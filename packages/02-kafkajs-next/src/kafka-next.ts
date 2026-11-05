/**
 * KafkaNext: High-level wrapper around kafkajs with TypeScript-first APIs.
 */

import {
  Kafka,
  KafkaConfig,
  Producer,
  ProducerRecord,
  Consumer,
  ConsumerConfig,
  EachMessagePayload,
  Admin,
  ClusterMetadata,
} from "kafkajs";
import { z, ZodSchema } from "zod";
import pino from "pino";

import { TypedProducer, createTypedProducer } from "./typed/producer";
import { TypedConsumer, createTypedConsumer } from "./typed/consumer";
import { TypedConsumerGroup, createConsumerGroup } from "./typed/consumer-group";
import { SchemaRegistry, SchemaRegistryConfig } from "./schema-registry";
import { MonitoringConfig, MetricsCollector, createMetricsCollector } from "./monitoring";
import { InstrumentedProducer, createInstrumentedProducer } from "./instrumentation";
import { RetryPolicy, DeadLetterQueue } from "./resilience";

export interface KafkaNextConfig extends KafkaConfig {
  /** Enable TypeScript schema validation */
  schemaValidation?: boolean;
  /** Schema Registry configuration */
  schemaRegistry?: SchemaRegistryConfig;
  /** Monitoring configuration */
  monitoring?: MonitoringConfig;
  /** Retry policy for failed operations */
  retryPolicy?: RetryPolicy;
  /** Dead letter queue configuration */
  deadLetterQueue?: DeadLetterQueue;
  /** Logger instance */
  logger?: pino.Logger;
}

export interface KafkaNext {
  kafka: Kafka;
  admin: Admin;
  producer: Producer;
  typedProducer: <T extends ZodSchema>(schema: T) => TypedProducer<T>;
  consumer: (config: ConsumerConfig) => Consumer;
  typedConsumer: <T extends ZodSchema>(config: ConsumerConfig, schema: T) => TypedConsumer<T>;
  consumerGroup: <T extends ZodSchema>(groupId: string, config: ConsumerConfig, schema: T) => TypedConsumerGroup<T>;
  metrics: MetricsCollector;
  schemaRegistry: SchemaRegistry;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
  healthCheck: () => Promise<HealthCheckResult>;
}

export interface HealthCheckResult {
  healthy: boolean;
  brokers: string[];
  latency: number;
  timestamp: Date;
  details: Record<string, unknown>;
}

function createLogger(config: KafkaNextConfig): pino.Logger {
  return config.logger || pino({
    level: process.env.LOG_LEVEL || "info",
    transport: process.env.NODE_ENV !== "production" ? {
      target: "pino-pretty",
      options: { colorize: true },
    } : undefined,
  });
}

export function createKafkaNext(config: KafkaNextConfig): KafkaNext {
  const logger = createLogger(config);
  const kafka = new Kafka(config);

  // Create admin client
  const admin = kafka.admin();

  // Create base producer
  const producer = kafka.producer({
    allowAutoCreateTopics: config.allowAutoCreateTopics ?? false,
    transactionTimeout: config.transactionTimeout ?? 30000,
  });

  // Create instrumented producer for monitoring
  const instrumentedProducer = createInstrumentedProducer(producer, logger);

  // Create metrics collector
  const metrics = createMetricsCollector(config.monitoring, logger);

  // Create schema registry
  const schemaRegistry = new SchemaRegistry(config.schemaRegistry, logger);

  // Wrap producer with instrumentation
  const wrappedProducer = {
    ...producer,
    send: async (record: ProducerRecord) => {
      const start = Date.now();
      try {
        const result = await instrumentedProducer.send(record);
        metrics.recordProduceLatency(Date.now() - start);
        metrics.incrementProducedMessages(record.messages.length);
        return result;
      } catch (error) {
        metrics.incrementProduceErrors();
        throw error;
      }
    },
    sendBatch: async (records: ProducerRecord[]) => {
      const start = Date.now();
      try {
        const result = await instrumentedProducer.sendBatch(records);
        const totalMessages = records.reduce((sum, r) => sum + r.messages.length, 0);
        metrics.recordProduceLatency(Date.now() - start);
        metrics.incrementProducedMessages(totalMessages);
        return result;
      } catch (error) {
        metrics.incrementProduceErrors();
        throw error;
      }
    },
  };

  return {
    kafka,
    admin,
    producer: wrappedProducer,
    typedProducer: createTypedProducer(wrappedProducer, schemaRegistry, config.retryPolicy),
    consumer: (consumerConfig: ConsumerConfig) => kafka.consumer(consumerConfig),
    typedConsumer: (consumerConfig: ConsumerConfig, schema: ZodSchema) =>
      createTypedConsumer(kafka.consumer(consumerConfig), schema, schemaRegistry, config.retryPolicy),
    consumerGroup: (groupId: string, consumerConfig: ConsumerConfig, schema: ZodSchema) =>
      createConsumerGroup(groupId, kafka.consumer({ ...consumerConfig, groupId }), schema, schemaRegistry, config.retryPolicy, config.deadLetterQueue),
    metrics,
    schemaRegistry,
    connect: async () => {
      await admin.connect();
      await producer.connect();
      logger.info("KafkaNext connected");
    },
    disconnect: async () => {
      await producer.disconnect();
      await admin.disconnect();
      logger.info("KafkaNext disconnected");
    },
    healthCheck: async () => {
      const start = Date.now();
      try {
        const metadata = await admin.fetchClusterMetadata();
        return {
          healthy: true,
          brokers: metadata.brokers.map(b => `${b.host}:${b.port}`),
          latency: Date.now() - start,
          timestamp: new Date(),
          details: {
            topics: metadata.topics.length,
            controller: metadata.controller?.nodeId,
          },
        };
      } catch (error) {
        return {
          healthy: false,
          brokers: [],
          latency: Date.now() - start,
          timestamp: new Date(),
          details: { error: error instanceof Error ? error.message : String(error) },
        };
      }
    },
  };
}