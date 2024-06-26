#!/bin/sh

# Package managers set this so we don't need to run
if [ -z "$DESTDIR" ]; then
  echo Compiling GSettings schemas...
  glib-compile-schemas ${MESON_INSTALL_PREFIX}/share/glib-2.0/schemas

  echo Updating icon cache...
  gtk-update-icon-cache -qtf ${MESON_INSTALL_PREFIX}/share/icons/hicolor
fi
