
from datetime import datetime
import requests
import queue
import threading
import requests
list_apis = {"paris": "https://opendata.paris.fr/api/explore/v2.1/catalog/datasets/velib-disponibilite-en-temps-reel/records",
           "lille": "https://opendata.lillemetropole.fr/api/explore/v2.1/catalog/datasets/vlille-realtime/records",
           "lyon": "https://transport.data.gouv.fr/gbfs/lyon/station_information.json",
           "strasbourg": "https://data.strasbourg.eu/api/explore/v2.1/catalog/datasets/stations-velhop/records",
           "toulouse": "https://data.toulouse-metropole.fr/api/explore/v2.1/catalog/datasets/api-velo-toulouse-temps-reel/records",
           "bordeaux": "https://transport.data.gouv.fr/gbfs/vcub/station_information.json",
           "nancy": "https://transport.data.gouv.fr/gbfs/nancy/station_information.json",
           "amiens": "https://transport.data.gouv.fr/gbfs/amiens/station_information.json",
           "besancon": "https://transport.data.gouv.fr/gbfs/besancon/station_information.json"}


def extract_from_opendata_thread(city, thread_id, number_of_threads, merged_results):
    offset = thread_id * 100
    results = []
    while True:
        url = list_apis[city] + "?limit=100&offset=" + str(offset)
        try:
            response = requests.get(url).json()
        except Exception as e:
            print(e)
            print("Error while calling API from opendata")
            exit(1)
        if (len(response["results"]) > 0):
            results = results + response["results"]
            offset += number_of_threads * 100
        else:
            break
    match city:
        case "lille":
            for station in results:
                station["station_id"] = station["libelle"]
                station["name"] = station["nom"]
                station["capacity"] = station["nbplacesdispo"]
                station["lat"] = station["geo"]["lat"]
                station["lon"] = station["geo"]["lon"]
                station["num_bikes_available"] = station["nbvelosdispo"]
                station["last_reported"] = datetime.strptime(
                    station["datemiseajour"][:-6], "%Y-%m-%dT%H:%M:%S").timestamp()
        case "strasbourg":
            for station in results:
                station["name"] = station["na"]
                station["capacity"] = station["to"]
                station["lat"] = station["la"]
                station["lon"] = station["lg"]
                station["num_bikes_available"] = station["av"]
                station["station_id"] = station["id"]
        case "toulouse":
            for station in results:
                station["station_id"] = station["number"]
                station["capacity"] = station["bike_stands"]
                station["lat"] = station["position"]["lat"]
                station["lon"] = station["position"]["lon"]
                station["num_bikes_available"] = station["available_bikes"]
                station["last_reported"] = datetime.strptime(
                    station["last_update"][:-6], "%Y-%m-%dT%H:%M:%S").timestamp()
        case default:
            for station in results:
                station["lat"] = station["coordonnees_geo"]["lat"]
                station["lon"] = station["coordonnees_geo"]["lon"]
                station["num_bikes_available"] = station["numbikesavailable"]
                station["station_id"] = station["stationcode"]
                station["last_reported"] = datetime.strptime(
                    station["duedate"][:-6], "%Y-%m-%dT%H:%M:%S").timestamp()
    merged_results.put(results)


def extract_from_opendata(city):
    merged_results = queue.Queue()
    total = 0
    url = list_apis[city]
    try:
        response = requests.get(url).json()
        total = response["total_count"]
    except Exception as e:
        print(e)
        print("Error while calling API from opendata")
        exit(1)
    number_of_pages = total // 100 + 1
    max_threads = 10
    number_of_threads = min(max_threads, number_of_pages)
    threads = []
    for i in range(number_of_threads):
        t = threading.Thread(target=extract_from_opendata_thread, args=(
            city, i, number_of_threads, merged_results))
        threads.append(t)
        t.start()
    for t in threads:
        t.join()

    stations = [station for sublist in list(
        merged_results.queue) for station in sublist]
    return {'stations': stations, 'city': city}


def extract_from_gouv(city):
    try:
        stations_informations = requests.get(list_apis[city]).json()
    except Exception as e:
        print(e)
        print("Error while calling API informations from gouv")
        exit(1)
    stations_informations = stations_informations["data"]["stations"]
    try:
        stations_status = requests.get(list_apis[city].replace(
            "station_information", "station_status")).json()
    except Exception as e:
        print(e)
        print("Error while calling API status from gouv")
        exit(1)
    stations_status = stations_status["data"]["stations"]
    stations_dict = {}
    for station in stations_informations:
        stations_dict[station["station_id"]] = station
    for station in stations_status:
        informations = stations_dict[station["station_id"]]
        station["name"] = informations["name"]
        station["lat"] = informations["lat"]
        station["lon"] = informations["lon"]
        station["capacity"] = informations["capacity"]

    return {'stations': stations_status, 'city': city}

def extract_from_api(city):
    if (list_apis[city].find(".json") == -1):
        print("extract from " + city + " opendata")
        result = extract_from_opendata(city)
    else:
        print("extract from " + city + " gouv")
        result = extract_from_gouv(city)
    return result
    
