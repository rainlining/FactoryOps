from __future__ import annotations

from confluent_kafka import Consumer, KafkaError, KafkaException, TopicPartition

from .model import KafkaRecord


class ConfluentKafkaConsumer:
    def __init__(self, consumer: Consumer) -> None:
        self._consumer = consumer

    def poll(self, timeout_seconds: float) -> KafkaRecord | None:
        message = self._consumer.poll(timeout_seconds)
        if message is None:
            return None
        if message.error():
            if message.error().code() == KafkaError._PARTITION_EOF:
                return None
            raise RuntimeError(str(message.error()))
        return KafkaRecord(
            topic=message.topic(),
            partition=message.partition(),
            offset=message.offset(),
            key=message.key(),
            value=message.value(),
        )

    def commit(self, record: KafkaRecord) -> None:
        offsets = [
            TopicPartition(
                record.topic,
                record.partition,
                record.offset + 1,
            )
        ]
        committed = self._consumer.commit(offsets=offsets, asynchronous=False)
        for offset in committed or ():
            if offset.error is not None:
                raise KafkaException(offset.error)

    def seek(self, record: KafkaRecord) -> None:
        self._consumer.seek(
            TopicPartition(record.topic, record.partition, record.offset)
        )

    def close(self) -> None:
        self._consumer.close()
