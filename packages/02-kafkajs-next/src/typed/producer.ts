/**
 * TypedProducer: Type-safe Kafka producer with Zod schema validation.
 */

import { Producer, ProducerRecord, KafkaMessage } from "kafkajs";
import { z, ZodSchema, ZodTypeAny, ZodError } from "zod";
import { SchemaRegistry } from "../schema-registry";
import { RetryPolicy } from "../resilience";
import pino from "pino";

export interface TypedProducer<T extends ZodSchema> {
  schema: T;
  send: (topic: string, message: z.infer<T>, key?: string, headers?: Record<string, string>) => Promise<void>;
  sendBatch: (topic: string, messages: z.infer<T>[], keys?: string[], headers?: Record<string, string>[]) => Promise<void>;
  sendRaw: (record: ProducerRecord) => Promise<void>;
}

export function createTypedProducer<T extends ZodSchema>(
  producer: Producer,
  schemaRegistry: SchemaRegistry,
  retryPolicy?: RetryPolicy
) {
  return function typedProducer<T extends ZodSchema>(schema: T): TypedProducer<T> {
    const logger = pino({ name: `typed-producer:${schema.description || "unknown"}` });

    async function validateAndSerialize(message: z.infer<T>): Promise<{ value: Buffer; schemaId?: number }> {
      // Validate with Zod
      const result = schema.safeParse(message);
      if (!result.success) {
        const error = new ZodError(result.error.errors);
        logger.error({ errors: error.errors }, "Schema validation failed");
        throw error;
      }

      // Serialize via Schema Registry if available
      if (schemaRegistry.isEnabled()) {
        const serialized = await schemaRegistry.serialize(schema, result.data);
        return { value: serialized.value, schemaId: serialized.schemaId };
      }

      // Fallback to JSON
      return { value: Buffer.from(JSON.stringify(result.data)) };
    }

    async function sendWithRetry(
      topic: string,
      message: z.infer<T>,
      key?: string,
      headers?: Record<string, string>
    ): Promise<void> {
      const { value, schemaId } = await validateAndSerialize(message);

      const record: ProducerRecord = {
        topic,
        messages: [{
          key: key ? Buffer.from(key) : undefined,
          value,
          headers: schemaId ? { "x-schema-id": Buffer.from(String(schemaId)) } : undefined,
          ...headers && Object.entries(headers).reduce((acc, [k, v]) => {
            acc[k] = Buffer.from(v);
            return acc;
          }, {} as Record<string, Buffer>),
        }],
      };

      const maxRetries = retryPolicy?.maxRetries ?? 3;
      const baseDelay = retryPolicy?.baseDelay ?? 1000;

      for (let attempt = 0; attempt <= maxRetries; attempt++) {
        try {
          await producer.send(record);
          return;
        } catch (error) {
          if (attempt === maxRetries) {
            logger.error({ error, attempt, topic }, "Failed to send message after retries");
            throw error;
          }
          const delay = baseDelay * Math.pow(2, attempt);
          logger.warn({ error, attempt, delay }, "Send failed, retrying");
          await new Promise(resolve => setTimeout(resolve, delay));
        }
      }
    }

    return {
      schema,
      async send(topic: string, message: z.infer<T>, key?: string, headers?: Record<string, string>) {
        await sendWithRetry(topic, message, key, headers);
      },
      async sendBatch(topic: string, messages: z.infer<T>[], keys?: string[], headers?: Record<string, string>[]) {
        const validatedMessages = await Promise.all(
          messages.map(async (msg, i) => {
            const { value, schemaId } = await validateAndSerialize(msg);
            return {
              key: keys?.[i] ? Buffer.from(keys[i]) : undefined,
              value,
              headers: schemaId
                ? { "x-schema-id": Buffer.from(String(schemaId)) }
                : undefined,
              ...headers?.[i] && Object.entries(headers[i]).reduce((acc, [k, v]) => {
                acc[k] = Buffer.from(v);
                return acc;
              }, {} as Record<string, Buffer>),
            };
          })
        );

        const record: ProducerRecord = { topic, messages: validatedMessages };

        const maxRetries = retryPolicy?.maxRetries ?? 3;
        const baseDelay = retryPolicy?.baseDelay ?? 1000;

        for (let attempt = 0; attempt <= maxRetries; attempt++) {
          try {
            await producer.send(record);
            return;
          } catch (error) {
            if (attempt === maxRetries) {
              logger.error({ error, attempt, topic, count: messages.length }, "Failed to send batch after retries");
              throw error;
            }
            const delay = baseDelay * Math.pow(2, attempt);
            logger.warn({ error, attempt, delay }, "Batch send failed, retrying");
            await new Promise(resolve => setTimeout(resolve, delay));
          }
        }
      },
      sendRaw: (record: ProducerRecord) => producer.send(record),
    };
  };
}