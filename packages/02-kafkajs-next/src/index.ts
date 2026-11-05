/**
 * kafkajs-next: TypeScript-first Kafka client with schema validation,
 * TypeScript consumer groups, and zero-config monitoring.
 *
 * A co-maintained fork/extension of kafkajs with:
 * - Full TypeScript support with Zod schema validation
 * - Type-safe consumer groups
 * - Built-in monitoring and metrics
 * - Schema Registry integration (Avro, Protobuf, JSON Schema)
 * - Automatic retry and dead letter handling
 */

export {
  Kafka,
  KafkaConfig,
  Producer,
  ProducerRecord,
  Consumer,
  ConsumerConfig,
  EachMessagePayload,
  Admin,
  AdminConfig,
  ClusterMetadata,
  TopicMetadata,
  PartitionMetadata,
} from "kafkajs";

// Re-export Zod for schema validation
export { z, ZodSchema, ZodTypeAny, ZodError } from "zod";

// kafkajs-next specific exports
export {
  TypedProducer,
  TypedConsumer,
  TypedConsumerGroup,
  SchemaRegistry,
  SchemaRegistryConfig,
  AvroSerializer,
  ProtobufSerializer,
  JsonSchemaSerializer,
  MonitoringConfig,
  MetricsCollector,
  HealthCheck,
  RetryPolicy,
  DeadLetterQueue,
  createTypedProducer,
  createTypedConsumer,
  createConsumerGroup,
} from "./typed";

export {
  KafkaNextConfig,
  KafkaNext,
  createKafkaNext,
} from "./kafka-next";

export {
  SchemaValidator,
  validateMessage,
  ValidationError,
} from "./validation";

export {
  InstrumentedProducer,
  InstrumentedConsumer,
  createInstrumentedProducer,
  createInstrumentedConsumer,
} from "./instrumentation";