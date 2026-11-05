/**
 * TypedConsumer: Type-safe Kafka consumer with Zod schema validation.
 */

import { Consumer, EachMessagePayload, KafkaMessage } from "kafkajs";
import { z, ZodSchema, ZodError } from "zod";
import { SchemaRegistry } from "../schema-registry";
import { RetryPolicy } from "../resilience";
import pino from "pino";

export interface TypedMessageHandler<T> {
  (message: z.infer<T>, payload: EachMessagePayload): Promise<void>;
}

export interface TypedConsumer<T extends ZodSchema> {
  schema: T;
  subscribe: (topic: string, fromBeginning?: boolean) => Promise<void>;
  run: (handler: TypedMessageHandler<T>) => Promise<void>;
  disconnect: () => Promise<void>;
  pause: (topics: string[]) => Promise<void>;
  resume: (topics: string[]) => Promise<void>;
}

export function createTypedConsumer<T extends ZodSchema>(
  consumer: Consumer,
  schema: T,
  schemaRegistry: SchemaRegistry,
  retryPolicy?: RetryPolicy
): TypedConsumer<T> {
  const logger = pino({ name: `typed-consumer:${schema.description || "unknown"}` });

  async function deserializeMessage(message: KafkaMessage): Promise<z.infer<T>> {
    // Deserialize via Schema Registry if available
    if (schemaRegistry.isEnabled() && message.headers?.["x-schema-id"]) {
      const schemaId = parseInt(message.headers["x-schema-id"].toString(), 10);
      const deserialized = await schemaRegistry.deserialize(schema, message.value!, schemaId);
      return deserialized;
    }

    // Fallback to JSON parsing + Zod validation
    let parsed: unknown;
    try {
      parsed = message.value ? JSON.parse(message.value.toString()) : null;
    } catch {
      throw new Error("Failed to parse message as JSON");
    }

    const result = schema.safeParse(parsed);
    if (!result.success) {
      const error = new ZodError(result.error.errors);
      logger.error({ errors: error.errors, topic: message.topic, partition: message.partition }, "Schema validation failed");
      throw error;
    }

    return result.data;
  }

  const maxRetries = retryPolicy?.maxRetries ?? 3;
  const baseDelay = retryPolicy?.baseDelay ?? 1000;

  return {
    schema,
    async subscribe(topic: string, fromBeginning = false) {
      await consumer.subscribe({ topic, fromBeginning });
      logger.info({ topic }, "Subscribed to topic");
    },
    async run(handler: TypedMessageHandler<T>) {
      await consumer.run({
        eachMessage: async (payload: EachMessagePayload) => {
          const { topic, partition, message } = payload;
          let attempt = 0;

          while (attempt <= maxRetries) {
            try {
              const typedMessage = await deserializeMessage(message);
              await handler(typedMessage, payload);
              return; // Success
            } catch (error) {
              attempt++;
              if (attempt > maxRetries) {
                logger.error({ error, topic, partition, offset: message.offset }, "Message processing failed after retries");
                // Could send to DLQ here
                throw error;
              }
              const delay = baseDelay * Math.pow(2, attempt - 1);
              logger.warn({ error, attempt, delay }, "Processing failed, retrying");
              await new Promise(resolve => setTimeout(resolve, delay));
            }
          }
        },
      });
    },
    async disconnect() {
      await consumer.disconnect();
      logger.info("Consumer disconnected");
    },
    async pause(topics: string[]) {
      consumer.pause(topics.map(t => ({ topic: t })));
      logger.info({ topics }, "Paused topics");
    },
    async resume(topics: string[]) {
      consumer.resume(topics.map(t => ({ topic: t })));
      logger.info({ topics }, "Resumed topics");
    },
  };
}