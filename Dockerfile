FROM xrally/xrally:3.0.0

# "rally" user (which is selected by-default) is owner of "/rally" directory,
#   so there is no need to call chown or switch the user
COPY . /rally/xrally_opentstack
WORKDIR /rally/xrally_opentstack

# to install package system-wide, we need to temporary switch to root user
USER root
# disabling cache since we do not expect to install other packages
RUN pip3 install -U setuptools --no-cache-dir && pip3 install . --no-cache-dir

# switch back to rally user for avoid permission conflicts
USER rally
