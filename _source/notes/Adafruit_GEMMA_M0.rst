Adafruit GEMMA M0
=================


Flashing
--------

To flash with Arduino (On Ubuntu 18.04):

 # In arduino software go to File -> Preferences and paste ``https://adafruit.github.io/arduino-board-index/package_adafruit_index.json`` into ``Additional Board Manager URLs``.
 # Go to Tools -> Board -> Board Manager and find and install ``Adafruit SAMD Boards``
 # Connect the board via USB and double press the reset button. This should turn the light green
 # In Arduino IDE go to Tools -> Board and select "**Adafruit** Gemma M0"
 # Try to upload. It might fail with the error: ``java.io.IOException: Cannot run program "{runtime.tools.bossac-1.7.0.path}/bossac": error=2, No such file or directory``
    # Find the bossac_linux executable on your system. It should be in ``~/.arduino15/packages/adafruit/hardware/samd/1.2.7/tools``
    # edit the file ``.arduino15/packages/adafruit/hardware/samd/1.2.7/platform.txt``, the .arduino15 directory is usually located in your home direcotry.
    # Change the value for ``tools.bossac.path`` to the directory of your bossac_linux executable (no trailing ``/``)
    # Change ``tools.bossac.cmd=bossac`` to ``tools.bossac.cmd=bossac_linux``
    # Restart Arduino IDE and retry upload

