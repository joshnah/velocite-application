import json
from kafka import KafkaConsumer


TOPIC_NAME = 'parsed_data'
SERVER_ADDRESS = 'localhost:9092'
CONSUMER_GROUP_ID = 'end_consumer'

#defining consumer 
consumer = KafkaConsumer(
    TOPIC_NAME,
    bootstrap_servers=SERVER_ADDRESS,
    group_id=CONSUMER_GROUP_ID
)

if __name__ == "__main__":
    """Consume Data from the consumer """

    try:
        for msg in consumer:
            print (json.loads(msg.value))
    except KeyboardInterrupt:
        print("-quit")


