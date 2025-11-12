# How to Install the NeuroLayer Project

The project is composed of two repositories:

- **NeuroLayerPlugin** – an Open Ephys plugin that provides a DLL library to be added to the Open Ephys plugin folder.  
- **HaeslerVisualization** – a web-based visualization panel.

---

## Step 1: Install Open Ephys

If Open Ephys is not already installed, install it first.

The web app uses the **Event Broadcaster** plugin, which must be installed from the **Open Ephys Plugin Store** (available inside the Open Ephys application).

---

## Step 2: Run the Installer

Double-click the `install.bat` file.  
This script will automatically:

- Download and install the necessary DLL library in the correct Open Ephys directory.  
- Install the web app and create an executable file (saved in .local), along with a shortcut on your desktop.

---

# How to Run the NeuroLayer Project

1. **Launch Open Ephys**, then add a source plugin:
   - **NeuroLayer Plugin** – for real-time acquisition using the NI-DAQ system.  
     - Load the configuration file that defines the station and hardware lines to be used.  
   - **Filesystem Plugin** – for replaying previously recorded (offline) data.

2. **Launch the Web App**
   - Double-click the desktop shortcut created during installation.  
   - The first launch may take a few minutes.  
   - Once ready, a new browser tab will open automatically.

---

# How to Use the NeuroLayer Project

After adding and configuring the NeuroLayer plugin, you don’t need to interact with Open Ephys directly.  
All further actions can be performed through the web app.

---

## Visualization Setup

- Choose the **number of columns and rows** for your probe layout.  
- The **divider** parameter allows you to display fewer cells than are actually used, helping to speed up visualization.  
- Click **Generate Visualization**.  
  - This process can take some time.  
  - You can adjust other parameters simultaneously, such as the folder where data will be saved.

---

## Event Configuration

Customize the **TTL event line** from which events are received.  
This should match the number defined in Open Ephys or in the configuration `.json` file used to set up the NeuroLayer plugin.

## Event Filtering

Customize the type of filtering to use it can be done offline as well after acquisition.

## Event creation 

Create a new event that combine the ones selected by averaging.

---

## ⚠️ Warning

If Open ephys stop recording by missing ram in the computer, it will display a notification but it won't be visible on the web app side. It will bug the web app as well as not recording your data. 

--> problem to fix for next time
It needs a communication with open ephys to stream the warning. 



### Issue known

- The panel lib is fixed for the moment to 1.7.2 as the next version (1.8) create display issue.
- 
