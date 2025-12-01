# Flame addon
Flame integration for AYON.

## Running Flame in Console
We are recommended to use the following command to launch Flame in a terminal:
Ideally save the content into a file named `flame2026.1.sh` anywhere at studio shared drive. Then add the file path to your application variant executable path. Make sure the the shell script is **chmod +x**. 

```sh
#!/bin/bash

# Launch terminal in Rocky Linux 9 and run an application
gnome-terminal -- bash -c "/opt/Autodesk/flame_2026.1/bin/startApplication; exec bash"
```
