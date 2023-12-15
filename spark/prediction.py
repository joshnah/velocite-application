from pyspark.sql import SparkSession
from pyspark.sql.window import Window
from pyspark.sql import functions as F
from pyspark.sql.functions import from_json, col, explode, from_unixtime,window,avg,date_format, expr
from pyspark.sql.types import StructType, StructField, StringType, IntegerType, DoubleType, ArrayType, TimestampType
import sys
# Define the schema for the Kafka message
schema = StructType([
    StructField("stations", ArrayType(StructType([
        StructField("is_installed", IntegerType(), True),
        StructField("is_renting", IntegerType(), True),
        StructField("is_returning", IntegerType(), True),
        StructField("last_reported", StringType(), True),
        StructField("num_bikes_available", IntegerType(), True),
        StructField("num_docks_available", IntegerType(), True),
        StructField("station_id", StringType(), True),
        StructField("name", StringType(), True),
        StructField("lat", DoubleType(), True),
        StructField("lon", DoubleType(), True),
        StructField("capacity", IntegerType(), True)
    ])), True),
    StructField("city", StringType(), True)
])

def write_to_cassandra(df, epoch_id):
    print("\nWriting to Cassandra...\n")
    df.write \
        .format("org.apache.spark.sql.cassandra") \
        .option("keyspace", "station") \
        .option("table", "stations") \
        .mode("append") \
        .save()
def main():
    CASSANDRA_HOST = sys.argv[1]
    CASSANDRA_PORT = sys.argv[2]

    # Create a Spark session
    spark = SparkSession.builder \
        .appName("Spark-Cassandra-App") \
        .config("spark.cassandra.connection.host", CASSANDRA_HOST) \
        .config("spark.cassandra.connection.port", CASSANDRA_PORT) \
        .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")

    # select * from station.weather and print result
    # spark.read \
    #     .format("org.apache.spark.sql.cassandra") \
    #     .options(table="weather", keyspace="station") \
    #     .load() \
    #     .show()
    
    # join station.weather and station.stations and print result (station.weather.city = station.stations.city and station.weather.forecast_date + INTERVAL 30 MINUTES <= station.stations.updated_at AND station.weather.forecast_date - INTERVAL 30 MINUTES >= station.stations.updated_at)
    
    # df_weather = spark.read.format("org.apache.spark.sql.cassandra").options(table="weather", keyspace="station").load()
    # df_stations = spark.read.format("org.apache.spark.sql.cassandra").options(table="stations", keyspace="station").load()

    # result = df_weather.join(df_stations.withColumnRenamed("updated_at", "stations_updated_at"), ["city"], "inner") \
    #     .where(expr("forecast_date + INTERVAL 30 MINUTES <= stations_updated_at") &
    #         expr("forecast_date - INTERVAL 30 MINUTES >= stations_updated_at"))

    df_stations = spark.read.format("org.apache.spark.sql.cassandra").options(table="stations", keyspace="station").load()

    # Define a window specification based on the "updated_at" column
    window_spec = Window.partitionBy("city", "station_id").orderBy("updated_at")

    # Calculate the difference between the current bikes and the previous bikes
    df_stations_diff = df_stations.withColumn("bikes_diff", F.col("bikes") - F.lag("bikes").over(window_spec))


    df_weather = spark.read.format("org.apache.spark.sql.cassandra").options(table="weather", keyspace="station").load()
    result = df_weather.join(df_stations_diff.withColumnRenamed("updated_at", "stations_updated_at"), ["city"], "inner") \
    .where(expr("forecast_date + INTERVAL 30 MINUTES <= stations_updated_at") &
        expr("forecast_date - INTERVAL 30 MINUTES >= stations_updated_at"))

    result = result.withColumn("hour_of_forecast", F.hour("forecast_date"))

    result_grouped = result.groupBy("station_id", "city", "hour_of_forecast").agg(
    F.first("bikes").alias("initial_bikes"),
    (F.avg(F.expr("bikes_diff * 100 / (100 - proba_rain)"))).alias("weighted_avg_bikes_diff")
)

    df_weather_forecast = df_weather\
        .withColumn("hour_of_forecast", F.hour("forecast_date")) \
        .where(expr("forecast_date >= current_timestamp()")) \
    
    df_final = df_weather_forecast.join(result_grouped, ["hour_of_forecast", "city"], "inner") 
    df_final = df_final.withColumn("prediction", F.col("initial_bikes") + F.coalesce(F.col("weighted_avg_bikes_diff"), F.lit(0)))

    window_forecast = Window.partitionBy("city", "station_id").orderBy("hour_of_forecast")

    df_final_diff = df_final.withColumn(
    "prediction",
    F.when(F.col("weighted_avg_bikes_diff") + F.lag("prediction").over(window_forecast) < 0, 0)
    .otherwise(F.col("weighted_avg_bikes_diff") + F.lag("prediction").over(window_forecast))
).withColumnRenamed("updated_at", "up_at").withColumnRenamed("forecast_date", "updated_at")
    df_final_diff.select("station_id", "city", "updated_at", "prediction").write \
    .format("org.apache.spark.sql.cassandra") \
    .options(table="stations", keyspace="station") \
    .mode("append") \
    .save()


if __name__ == "__main__":
    main()