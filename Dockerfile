FROM xrally/xrally:3.2.0

# "rally" user (which is selected by-default) is owner of "/rally" directory,
#   so there is no need to call chown or switch the user
COPY . /rally/xrally_openstack
WORKDIR /rally/xrally_openstack

# to install package system-wide, we need to temporary switch to root user
USER root
# ensure that we have all system packages installed
RUN pip3 install --no-cache-dir -U bindep && apt update && apt install --yes $(bindep -b | tr '\n' ' ') && apt clean
# disabling cache since we do not expect to install other packages
RUN pip3 install . --no-cache-dir --constraint ./upper-constraints.txt

# switch back to rally user for avoid permission conflicts
USER rally
