install_data(
    'org.x.sticky.service',
    install_dir: datadir / 'dbus-1' / 'services',
)

i18n.merge_file(
    input: 'sticky.desktop.in',
    output: 'sticky.desktop',
    po_dir: podir,
    type: 'desktop',
    install: true,
    install_dir: datadir / 'applications',
)
