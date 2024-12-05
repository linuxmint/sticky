project('sticky', version : '1.23', meson_version : '>= 0.49.0')

i18n = import('i18n')

gettext_package = meson.project_name()

prefix = get_option('prefix')
bindir = get_option('bindir')
datadir = get_option('datadir')
sysconfdir = get_option('sysconfdir')

podir = meson.source_root() / 'po'

subdir('data')
subdir('po')

install_subdir('etc', install_dir: sysconfdir, strip_directory: true)
install_subdir('usr', install_dir: prefix, strip_directory: true)

meson.add_install_script('meson/meson-postinstall.sh')
