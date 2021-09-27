# Sticky Notes
Sticky Notes replaces GNote as the default application for taking notes. Similar to GNote, Sticky is developed in GTK3, supports HiDPI and integrates very well in the desktop environment. In addition to the features which were present in GNote, Sticky also lets you place the notes on the desktop and quickly access them from the icon tray.

![img](https://linuxmint.com/pictures/screenshots/uma/sticky.png)


## How to build and install

### Download the source code and enter the source directory
```
# Clone this repo:
git clone https://github.com/collinss/sticky.git

# Enter the folder:
cd sticky
```
### Mint, Debian, Ubuntu and derivatives:
```
# Try to build. If this fails, it's probably due to missing dependencies.
# Take note of these packages, install them using apt-get:
dpkg-buildpackage --no-sign

# Once that succeeds, install:
cd ..
sudo dpkg -i sticky*.deb

# If this fails, make note of missing runtime dependencies (check list below),
# install them, repeat previous command (apt-get install -f may also work).
```
### Otherwise (and this is valid anywhere if you want to avoid packaging):
```
sudo cp -r usr/ /usr/
sudo cp etc/xdg/autostart/sticky.desktop /etc/xdg/autostart/
```

#### runtime deps
- gir1.2-glib-2.0
- gir1.2-gtk-3.0 (>= 3.20.0)
- gir1.2-xapp-1.0 (>= 1.6.0)
- gir1.2-gspell-1
- python3
- python3-gi
- python3-xapp (>= 1.6.0)

## Translations
Please use Launchpad to translate Mintbackup: https://translations.launchpad.net/linuxmint/latest/.

The PO files in this project are imported from there.

## License
- Code: GPLv2
