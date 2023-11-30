service_conf = configuration_data()
service_conf.set('bindir', prefix / bindir)

configure_file(
    input: 'org.x.sticky.service.in',
    output: 'org.x.sticky.service',
    configuration: service_conf,
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
