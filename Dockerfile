FROM xrally/xrally:3.1.0

# "rally" user (which is selected by-default) is owner of "/rally" directory,
#   so there is no need to call chown or switch the user
COPY . /rally/xrally_opentstack
WORKDIR /rally/xrally_opentstack

# to install package system-wide, we need to temporary switch to root user
USER root
# ensure that we have all system packages installed
# NOTE(andreykurilin): we need to update setuptools, since xrally/xrally:3.0.0
#   has incompatible setuptools version for google-auth library
RUN pip3 install -U bindep && apt update && apt install --yes $(bindep -b | tr '\n' ' ') && apt clean
# disabling cache since we do not expect to install other packages
RUN pip3 install . --no-cache-dir --constraint ./upper-constraints.txt

# switch back to rally user for avoid permission conflicts
USER rally
