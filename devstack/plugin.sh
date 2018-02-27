# DevStack extras script to install Rally

# Save trace setting
XTRACE=$(set +o | grep xtrace)
set -o xtrace

DIR=$(dirname ${BASH_SOURCE[0]})
source $DIR/lib/rally

if [[ "$1" == "stack" && "$2" == "install" ]]; then
    echo_summary "Installing Rally-OpenStack"
    install_rally
elif [[ "$1" == "stack" && "$2" == "post-config" ]]; then
    echo_summary "Configuring Rally-OpenStack"
    configure_rally
elif [[ "$1" == "stack" && "$2" == "extra" ]]; then
    echo_summary "Initializing Rally-OpenStack"
    init_rally
fi

# Restore xtrace
$XTRACE
