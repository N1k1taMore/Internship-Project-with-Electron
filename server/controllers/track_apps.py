import psutil
import socket
import winsound
import pywifi
import time
from datetime import datetime
from sklearn.metrics import r2_score
from sklearn.model_selection import train_test_split
from pymongo import MongoClient
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from sklearn.linear_model import LinearRegression
from scapy.all import sniff, IP
from browser_history import get_history
import numpy as np

# MongoDB connection
mongo_url = 'mongodb+srv://manav2031:Ma310703@cluster0.8n47utm.mongodb.net/internship_project'
client = MongoClient(mongo_url)

def get_running_processes():
    """Retrieve a list of currently running processes."""
    running_processes = []
    for process in psutil.process_iter(['pid', 'name', 'create_time']):
        try:
            running_processes.append((process.info['pid'], process.info['name'], process.info['create_time']))
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return running_processes

def play_high_volume_sound():
    """Play a high volume sound when a browser is closed."""
    frequency = 2500  # Set the frequency of the sound (in Hz)
    duration = 1000   # Set the duration of the sound (in milliseconds)
    winsound.Beep(frequency, duration)  # Play the sound on Windows

def close_all_browsers():
    # List of browser process names
    browsers = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'safari.exe']  # For Windows
    
    # On macOS or Linux, the process names might be different (e.g., 'google-chrome', 'firefox', 'safari')
    # browsers = ['google-chrome', 'firefox', 'safari']

    # Iterate through all running processes
    for proc in psutil.process_iter(attrs=['pid', 'name']):
        try:
            if proc.info['name'] in browsers:  # Check if the process is one of the browsers
                proc.terminate()  # Terminate the browser process
                print(f"Terminated browser process: {proc.info['name']} (PID: {proc.info['pid']})")
                play_high_volume_sound()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass  # Handle processes that might terminate while we're iterating

def resolve_ip_to_host(ip_address):
    """Resolve an IP address to a hostname."""
    try:
        return socket.gethostbyaddr(ip_address)[0]
    except socket.herror:
        return None

def capture_network_requests(packet, mac_address):
    """Capture network requests and store source and destination details in MongoDB."""
    if IP in packet:
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst

        # Try to resolve IPs to hostnames (URLs)
        src_url = resolve_ip_to_host(src_ip)
        dst_url = resolve_ip_to_host(dst_ip)

        print(f"Network request captured:")
        print(f"Source IP: {src_ip} ({src_url if src_url else 'N/A'})")
        print(f"Destination IP: {dst_ip} ({dst_url if dst_url else 'N/A'})")
        print("-" * 40)

        # Store the network request details in MongoDB
        db = client[mac_address]
        collection = db[f'network_requests_{mac_address}']
        request_details = {
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'source_ip': src_ip,
            'source_url': src_url if src_url else 'N/A',
            'destination_ip': dst_ip,
            'destination_url': dst_url if dst_url else 'N/A'
        }
        collection.insert_one(request_details)

def start_network_capture(mac_address):
    """Start capturing network requests."""
    print("Starting network packet capture...")
    sniff(filter="ip", prn=lambda x: capture_network_requests(x, mac_address), store=0)


def collect_network_details(mac_address):
    """Collect and store network details in MongoDB."""
    db = client[mac_address]
    collection = db[f'network_details_{mac_address}']

    network_info = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    for interface, addrs in psutil.net_if_addrs().items():
        details = {
            'timestamp': current_time,
            'interface': interface,
            'ip_address': None,
            'netmask': None,
            'broadcast': None
        }
        for addr in addrs:
            if addr.family == socket.AF_INET:
                details['ip_address'] = addr.address
                details['netmask'] = addr.netmask
                details['broadcast'] = addr.broadcast

        if details['ip_address']:
            network_info.append(details)

    if network_info:
        collection.insert_many(network_info)

    print(f"Network details updated for MAC address {mac_address}.")

def collect_connected_devices(mac_address):
    """Collect and store connected devices details in MongoDB and handle device removal."""
    db = client[mac_address]
    collection = db[f'connected_devices_details_{mac_address}']

    # Load previously stored devices from the database
    previous_devices = {doc['Device Name']: doc for doc in collection.find()}

    wifi = pywifi.PyWiFi()
    iface = wifi.interfaces()[0]
    iface.scan()
    time.sleep(2)
    scan_results = iface.scan_results()

    connected_devices = []
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    pen_drive_detected = False

    # Collect Wi-Fi devices
    for device in scan_results:
        cleaned_device_name = device.ssid.strip()
        cleaned_mac_address = device.bssid.replace(':', '').upper()

        device_info = {
            'timestamp': current_time,
            'Device Type': 'Wi-Fi',
            'Device Name': cleaned_device_name,
            'MAC Address': cleaned_mac_address,
            'Signal Strength': device.signal
        }

        connected_devices.append(device_info)

    # Collect removable storage devices (e.g., pen drives)
    partitions = psutil.disk_partitions()
    for partition in partitions:
        if 'removable' in partition.opts:
            usage = psutil.disk_usage(partition.mountpoint)
            storage_info = {
                'timestamp': current_time,
                'Device Type': 'Secondary Storage',
                'Device Name': partition.device,
                'Mount Point': partition.mountpoint,
                'File System Type': partition.fstype,
                'Total Size (GB)': usage.total / (1024 ** 3),
                'Used Size (GB)': usage.used / (1024 ** 3),
                'Free Size (GB)': usage.free / (1024 ** 3)
            }
            connected_devices.append(storage_info)
            pen_drive_detected = True

    # Print connected devices details
    for device in connected_devices:
        print(f"Device Type: {device['Device Type']}")
        print(f"Device Name: {device.get('Device Name', 'N/A')}")
        print(f"MAC Address: {device.get('MAC Address', 'N/A')}")
        print(f"Signal Strength: {device.get('Signal Strength', 'N/A')}")
        print(f"Mount Point: {device.get('Mount Point', 'N/A')}")
        print(f"File System Type: {device.get('File System Type', 'N/A')}")
        print(f"Total Size (GB): {device.get('Total Size (GB)', 'N/A')}")
        print(f"Used Size (GB): {device.get('Used Size (GB)', 'N/A')}")
        print(f"Free Size (GB): {device.get('Free Size (GB)', 'N/A')}")
        print("-" * 40)

    # Remove entries for devices that are no longer connected
    current_device_names = {device['Device Name'] for device in connected_devices}
    for device_name in previous_devices:
        if device_name not in current_device_names:
            print(f"Removing device {device_name} from database.")
            collection.delete_many({'Device Name': device_name})

    # Print message if a pen drive is detected
    if pen_drive_detected:
        print("Pen drive detected.")

    # Store connected devices in MongoDB
    if connected_devices:
        collection.insert_many(connected_devices)

    print(f"Connected devices details updated for MAC address {mac_address}.")

def collect_application_usage(mac_address):
    """Collect and store application usage data in MongoDB."""
    print(f"Tracking MAC address: {mac_address}")
    db = client[mac_address]
    collection = db[f'process_details_{mac_address}']

    while True:
        running_processes = get_running_processes()
        current_time = datetime.now()

        entries = []
        for pid, name, create_time in running_processes:
            start_time = datetime.fromtimestamp(create_time)
            duration_seconds = (current_time - start_time).total_seconds()
            duration_minutes = duration_seconds / 60

            entry = {
                'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
                'pid': pid,
                'name': name,
                'duration_minutes': duration_minutes
            }
            entries.append(entry)

        if entries:
            collection.insert_many(entries)

        print(f"Application usage data updated for MAC address {mac_address} at {current_time}")


def collect_system_health_data():
    """Collect system health data like CPU, memory, and disk usage."""
    cpu_usage = psutil.cpu_percent(interval=1)
    memory_info = psutil.virtual_memory()
    disk_usage = psutil.disk_usage('/')
    
    return {
        'cpu_usage': cpu_usage,
        'memory_used': memory_info.used,
        'memory_total': memory_info.total,
        'disk_used': disk_usage.used,
        'disk_total': disk_usage.total,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def collect_system_health_for_ml(mac_address):
    """Store system health data for machine learning."""
    db = client[mac_address]
    collection = db[f'system_health_{mac_address}']
    
    health_data = collect_system_health_data()
    collection.insert_one(health_data)

def train_predictive_model(mac_address):
    """Train the machine learning model for predictive maintenance."""
    db = client[mac_address]
    collection = db[f'system_health_{mac_address}']
    
    # Load data from MongoDB
    data = list(collection.find())
    if len(data) < 10:  # Ensure we have enough data to train
        print("Not enough data to train the model.")
        return None
    
    # Prepare data for model training
    X = []
    y = []
    
    for record in data:
        X.append([record['cpu_usage'], record['memory_used'], record['disk_used']])
        y.append(record['cpu_usage'])
    
    X = np.array(X)
    y = np.array(y)
    
    # Split the data into train and test sets (80% train, 20% test)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Train the model
    model = LinearRegression()
    model.fit(X_train, y_train)
    
    # Make predictions on both the training and test data
    train_predictions = model.predict(X_train)
    test_predictions = model.predict(X_test)
    
    # Calculate and print R-squared values
    train_accuracy = r2_score(y_train, train_predictions)
    test_accuracy = r2_score(y_test, test_predictions)
    
    print(f"Model accuracy on training data (R-squared): {train_accuracy:.2f}")
    print(f"Model accuracy on test data (R-squared): {test_accuracy:.2f}")
    
    return model

def predict_failure(mac_address, model):
    """Use the trained model to predict potential failures."""
    health_data = collect_system_health_data()
    X_new = np.array([[health_data['cpu_usage'], health_data['memory_used'], health_data['disk_used']]])
    
    # Predict failure likelihood based on current system state
    prediction = model.predict(X_new)[0]
    
    # If CPU usage is predicted to exceed a threshold, trigger an alert
    if prediction > 90:  # Example threshold, you can adjust this
        print(f"Warning: High CPU usage predicted ({prediction:.2f}%)! System might require maintenance soon.")
        db = client[mac_address]
        alert_collection = db[f'failure_alerts_{mac_address}']
        alert_collection.insert_one({
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'predicted_cpu_usage': prediction,
            'alert': 'High CPU usage predicted. Possible maintenance required.'
        })

# Start monitoring system health data and train/predict with ML model
def monitor_with_ml(mac_address):
    """Collect system health data and predict failures using machine learning."""
    model = None
    while True:
        collect_system_health_for_ml(mac_address)
        
        # Train model every 10 iterations (can adjust this frequency)
        if not model or int(time.time()) % 10 == 0:
            model = train_predictive_model(mac_address)
        
        # Make failure prediction if model exists
        if model:
            predict_failure(mac_address, model)


def retrieve_browser_history(mac_address):
    """Retrieve and store browser history details in MongoDB."""
    start_time = datetime.now()
    date_only = start_time.strftime('%Y-%m-%d')
    db = client[mac_address]
    collection = db[f'browser_history_{mac_address}']

    # Clear any existing browser history data when the script starts
    try:
        collection.delete_many({})  # Delete all documents from the collection
    except Exception:
        return

    # Get the browser history
    try:
        history = get_history()  # Assuming get_history is defined elsewhere
    except Exception:
        return

    if not history:
        return

    history_data = history.histories

    if not history_data:
        return

    entries = []

    # Function to validate entries (e.g., check for valid URL)
    def is_valid_entry(entry):
        """Check if the entry is valid."""
        if isinstance(entry, tuple) and len(entry) >= 2:
            timestamp, url, title = entry[:3]  # Extract only the first two elements (timestamp, url)
            # Check if the URL is valid
            if not isinstance(url, str) or not url.startswith('http'):
                return False
            return True
        return False

    # Iterate through the history data and filter out invalid entries
    for entry in history_data:
        if is_valid_entry(entry):
            timestamp, url, title = entry[:3]  # Extract the timestamp and url
            # Convert timestamp to a string in the desired format
            timestamp_str = timestamp.strftime('%Y-%m-%d %H:%M:%S')
            timestamp_dt = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
            timestamp_date_only = timestamp_dt.strftime('%Y-%m-%d')
            if timestamp_date_only >= date_only:
                entry_data = {
                    'timestamp': timestamp_str,
                    'url': url,
                    'title': title
                }
                entries.append(entry_data)

    # Insert only valid entries into the collection
    if entries:
        try:
            result = collection.insert_many(entries)
        except Exception:
            return

    # Check if collection exists after insertion
    if collection.count_documents({}) > 0:
        return
    else:
        return


class FileChangeHandler(FileSystemEventHandler):
    """Handle file system events."""
    def on_modified(self, event):
        if not event.is_directory:
            print(f"File modified: {event.src_path}")

    def on_created(self, event):
        if not event.is_directory:
            print(f"File created: {event.src_path}")

    def on_deleted(self, event):
        if not event.is_directory:
            print(f"File deleted: {event.src_path}")

if __name__ == "__main__":
    mac_address = input("Enter the MAC address to track: ")
    
    # Start monitoring in separate threads
    import threading

    def monitor_network_details():
        while True:
            collect_network_details(mac_address)
            time.sleep(10)  # Check every 5 minutes

    def monitor_connected_devices():
        while True:
            collect_connected_devices(mac_address)
            time.sleep(10)  # Check every 5 minutes

    def monitor_application_usage():
        while True:
            collect_application_usage(mac_address)
            time.sleep(10)

    def monitor_machine_learning():
        while True:
            monitor_with_ml(mac_address)
            time.sleep(10)

    def monitor_network_requests():
        while True:
            start_network_capture(mac_address)
            time.sleep(10)

    def monitor_browser_history():
        while True:
            retrieve_browser_history(mac_address)
            time.sleep(10)

    def monitor_all_browsers():
        while True:
            close_all_browsers()
            time.sleep(10)

    # Start threads for monitoring
    threading.Thread(target=monitor_network_details, daemon=True).start()
    threading.Thread(target=monitor_connected_devices, daemon=True).start()
    threading.Thread(target=monitor_application_usage, daemon=True).start()
    threading.Thread(target=monitor_machine_learning, daemon=True).start()
    threading.Thread(target=monitor_network_requests, daemon=True).start()
    threading.Thread(target=monitor_browser_history, daemon=True).start()
    threading.Thread(target=monitor_all_browsers, daemon=True).start()

    # Set up file system monitoring
    path_to_watch = "."  # Monitor the current directory
    event_handler = FileChangeHandler()
    observer = Observer()
    observer.schedule(event_handler, path_to_watch, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()



# import psutil
# import socket
# import pywifi
# import time
# from datetime import datetime
# from pymongo import MongoClient
# from watchdog.observers import Observer
# from watchdog.events import FileSystemEventHandler

# # MongoDB connection
# mongo_url = 'mongodb+srv://manav2031:Ma310703@cluster0.8n47utm.mongodb.net/internship_project'
# client = MongoClient(mongo_url)

# def get_mac_address():
#     """Automatically get the MAC address of the machine, excluding loopback and virtual interfaces."""
#     for interface, addrs in psutil.net_if_addrs().items():
#         if interface != "lo":  # Exclude loopback
#             for addr in addrs:
#                 if addr.family == psutil.AF_LINK and not addr.address.startswith("00:00:00"):  # Check for valid MAC
#                     return addr.address.replace(':', '_').upper()
#     return None  # Return None if no valid MAC address is found


# def get_running_processes():
#     """Retrieve a list of currently running processes."""
#     running_processes = []
#     for process in psutil.process_iter(['pid', 'name', 'create_time']):
#         try:
#             running_processes.append((process.info['pid'], process.info['name'], process.info['create_time']))
#         except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
#             continue
#     return running_processes

# def collect_network_details(mac_address):
#     """Collect and store network details in MongoDB."""
#     db = client[mac_address]
#     collection = db[f'network_details_{mac_address}']

#     network_info = []
#     current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#     for interface, addrs in psutil.net_if_addrs().items():
#         details = {
#             'timestamp': current_time,
#             'interface': interface,
#             'ip_address': None,
#             'netmask': None,
#             'broadcast': None
#         }
#         for addr in addrs:
#             if addr.family == socket.AF_INET:
#                 details['ip_address'] = addr.address
#                 details['netmask'] = addr.netmask
#                 details['broadcast'] = addr.broadcast

#         if details['ip_address']:
#             network_info.append(details)

#     if network_info:
#         collection.insert_many(network_info)

#     print(f"Network details updated for MAC address {mac_address}.")

# def collect_connected_devices(mac_address):
#     """Collect and store connected devices details in MongoDB and handle device removal."""
#     db = client[mac_address]
#     collection = db[f'connected_devices_details_{mac_address}']

#     # Load previously stored devices from the database
#     previous_devices = {doc['Device Name']: doc for doc in collection.find()}

#     wifi = pywifi.PyWiFi()
#     iface = wifi.interfaces()[0]
#     iface.scan()
#     time.sleep(2)
#     scan_results = iface.scan_results()

#     connected_devices = []
#     current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
#     pen_drive_detected = False

#     # Collect Wi-Fi devices
#     for device in scan_results:
#         cleaned_device_name = device.ssid.strip()
#         cleaned_mac_address = device.bssid.replace(':', '').upper()

#         device_info = {
#             'timestamp': current_time,
#             'Device Type': 'Wi-Fi',
#             'Device Name': cleaned_device_name,
#             'MAC Address': cleaned_mac_address,
#             'Signal Strength': device.signal
#         }

#         connected_devices.append(device_info)

#     # Collect removable storage devices (e.g., pen drives)
#     partitions = psutil.disk_partitions()
#     for partition in partitions:
#         if 'removable' in partition.opts:
#             usage = psutil.disk_usage(partition.mountpoint)
#             storage_info = {
#                 'timestamp': current_time,
#                 'Device Type': 'Secondary Storage',
#                 'Device Name': partition.device,
#                 'Mount Point': partition.mountpoint,
#                 'File System Type': partition.fstype,
#                 'Total Size (GB)': usage.total / (1024 ** 3),
#                 'Used Size (GB)': usage.used / (1024 ** 3),
#                 'Free Size (GB)': usage.free / (1024 ** 3)
#             }
#             connected_devices.append(storage_info)
#             pen_drive_detected = True

#     # Print connected devices details
#     for device in connected_devices:
#         print(f"Device Type: {device['Device Type']}")
#         print(f"Device Name: {device.get('Device Name', 'N/A')}")
#         print(f"MAC Address: {device.get('MAC Address', 'N/A')}")
#         print(f"Signal Strength: {device.get('Signal Strength', 'N/A')}")
#         print(f"Mount Point: {device.get('Mount Point', 'N/A')}")
#         print(f"File System Type: {device.get('File System Type', 'N/A')}")
#         print(f"Total Size (GB): {device.get('Total Size (GB)', 'N/A')}")
#         print(f"Used Size (GB): {device.get('Used Size (GB)', 'N/A')}")
#         print(f"Free Size (GB): {device.get('Free Size (GB)', 'N/A')}")
#         print("-" * 40)

#     # Remove entries for devices that are no longer connected
#     current_device_names = {device['Device Name'] for device in connected_devices}
#     for device_name in previous_devices:
#         if device_name not in current_device_names:
#             print(f"Removing device {device_name} from database.")
#             collection.delete_many({'Device Name': device_name})

#     # Print message if a pen drive is detected
#     if pen_drive_detected:
#         print("Pen drive detected.")

#     # Store connected devices in MongoDB
#     if connected_devices:
#         collection.insert_many(connected_devices)

#     print(f"Connected devices details updated for MAC address {mac_address}.")

# def collect_application_usage(mac_address):
#     """Collect and store application usage data in MongoDB."""
#     print(f"Tracking MAC address: {mac_address}")
#     db = client[mac_address]
#     collection = db[f'process_details_{mac_address}']

#     while True:
#         running_processes = get_running_processes()
#         current_time = datetime.now()

#         entries = []
#         for pid, name, create_time in running_processes:
#             start_time = datetime.fromtimestamp(create_time)
#             duration_seconds = (current_time - start_time).total_seconds()
#             duration_minutes = duration_seconds / 60

#             entry = {
#                 'timestamp': current_time.strftime('%Y-%m-%d %H:%M:%S'),
#                 'pid': pid,
#                 'name': name,
#                 'duration_minutes': duration_minutes
#             }
#             entries.append(entry)

#         if entries:
#             collection.insert_many(entries)

#         print(f"Application usage data updated for MAC address {mac_address} at {current_time}")

# class FileChangeHandler(FileSystemEventHandler):
#     """Handle file system events."""
#     def on_modified(self, event):
#         if not event.is_directory:
#             print(f"File modified: {event.src_path}")

#     def on_created(self, event):
#         if not event.is_directory:
#             print(f"File created: {event.src_path}")

#     def on_deleted(self, event):
#         if not event.is_directory:
#             print(f"File deleted: {event.src_path}")

# if __name__ == "__main__":
#     mac_address = get_mac_address()
    
#     # Start monitoring in separate threads
#     import threading

#     def monitor_network_details():
#         while True:
#             collect_network_details(mac_address)
#             time.sleep(10)  # Check every 5 minutes

#     def monitor_connected_devices():
#         while True:
#             collect_connected_devices(mac_address)
#             time.sleep(10)  # Check every 5 minutes

#     def monitor_application_usage():
#         while True:
#             collect_application_usage(mac_address)
#             time.sleep(10)

#     # Start threads for monitoring
#     threading.Thread(target=monitor_network_details, daemon=True).start()
#     threading.Thread(target=monitor_connected_devices, daemon=True).start()
#     threading.Thread(target=monitor_application_usage, daemon=True).start()

#     # Set up file system monitoring
#     path_to_watch = "."  # Monitor the current directory
#     event_handler = FileChangeHandler()
#     observer = Observer()
#     observer.schedule(event_handler, path_to_watch, recursive=True)
#     observer.start()

#     try:
#         while True:
#             time.sleep(1)
#     except KeyboardInterrupt:
#         observer.stop()
#     observer.join()

