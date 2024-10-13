from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from multiprocessing import Process
import mimetypes
import json
import urllib.parse
import pathlib
import socket
import logging

from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

logger = logging.getLogger(__name__)

uri = "mongodb://mongodb:27017"

HTTPServer_Port = 3000
UDP_IP = "127.0.0.1"
UDP_PORT = 5000


class HttpGetHandler(BaseHTTPRequestHandler):

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))
        print(data)
        data_parse = urllib.parse.unquote_plus(data.decode())
        print(data_parse)
        data_dict = {
            key: value for key, value in [el.split("=") for el in data_parse.split("&")]
        }
        print(data_dict)
        self.send_response(302)
        self.send_header("Location", "/")
        self.end_headers()

    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("index.html")
        elif pr_url.path == "/message":
            self.send_html_file("message.html")
        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file("error.html", 404)

    def send_html_file(self, filename, status_code=200):

        file_path = pathlib.Path(__file__).parent / filename
        self.send_response(status_code)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        try:
            logger.info(f"Attempting to access file: {file_path.resolve()}")
            with open(file_path, "rb") as fd:
                self.wfile.write(fd.read())
        except FileNotFoundError:
            logger.error(f"File not found: {file_path}")
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h1>404 Not Found</h1><p>The requested file could not be found.</p>"
            )

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", "text/plain")
        self.end_headers()

        file_path = pathlib.Path(__file__).parent / self.path.lstrip("/")
        try:
            with open(file_path, "rb") as file:
                self.wfile.write(file.read())
        except FileNotFoundError:
            logger.error(f"Static file not found: {file_path}")
            self.send_response(404)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"<h1>404 Not Found</h1><p>The requested static file could not be found.</p>"
            )


def run_http_server(server_class=HTTPServer, handler_class=HttpGetHandler):
    server_address = ("0.0.0.0", HTTPServer_Port)
    http = server_class(server_address, handler_class)

    try:
        http.serve_forever()
        logger.info("Server is running")
    except KeyboardInterrupt:
        logger.warning(f"Error: {KeyboardInterrupt}")
        http.server_close()


def send_data_to_socket(data):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = UDP_IP, UDP_PORT
    # TODO Дописати відправку даних
    for line in data.split(" "):
        cdata = line.encode()
        sock.sendto(cdata, server)
        print(f"Send data: {cdata.decode()} to server: {server}")
        response, address = sock.recvfrom(1024)
        print(f"Response data: {response.decode()} from address: {address}")
    sock.close()


def save_data(data):
    client = MongoClient(uri, server_api=ServerApi("1"))
    db = client.mongodb
    collection = db["messages"]

    data_parse = urllib.parse.unquote_plus(data.decode())
    try:
        username, message = data_parse.split(",")
    except ValueError:

        print(f"Error parsing data: {data_parse}")
        return

    document = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"),
        "username": username.strip(),
        "message": message.strip(),
    }
    try:
        collection.insert_one(document)
        print(f"Data saved to MongoDB: {document}")
    except Exception as e:
        print(f"Error saving data to MongoDB: {e}")


def run_socket_server(ip, port):
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server = ip, port
    sock.bind(server)

    try:
        while True:
            data, address = sock.recvfrom(1024)
            print(f"Received data: {data.decode()} from: {address}")
            sock.sendto(data, address)
            print(f"Send data: {data.decode()} to: {address}")

    except KeyboardInterrupt:
        print(f"Destroy server")
    finally:
        sock.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(threadName)s %(message)s")

    http_server_process = Process(target=run_http_server)
    http_server_process.start()

    socket_server_process = Process(target=run_socket_server)
    socket_server_process.start()

    http_server_process.join()
    socket_server_process.join()
