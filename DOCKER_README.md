# What is Rally-OpenSack/xRally-OpenStack

Rally is tool & framework that allows one to write simple plugins and combine
them in complex tests scenarios that allows to perform all kinds of testing!

Rally-OpenStack is a package of Rally plugins for OpenStack platform. 

# How to run and use xrally-openstack container

First of all, you need to pull the container. We suggest to use the last
tagged version:

    # pull the 2.0.0 image (the latest release at the point of writing the note)
    $ docker pull xrally/xrally-openstack:2.0.0

**WARNING: never attach folders and volumes to `/rally` inside the container. It can break everything.**

The default configuration file is located at `/etc/rally/rally.conf`. You
should not be aware of it. If you want to override some options, use
`/home/rally/.rally/rally.conf` location instead. Rally does not load all
configuration files, so the primary one will be used.

The default place for rally database file is `/home/rally/.rally/rally.sqlite`.
To make the storage persistent across all container runs, you may want to use
docker volumes or mount the directory.

* use docker volumes. It is the easiest way. You just need to do something like:

      $ docker volume create --name rally_volume
      $ docker run -v rally_volume:/home/rally/.rally xrally/xrally-openstack:2.0.0 env create --name "foo"

* mount outer directory inside the container

      # you can create directory in whatever you want to place, but you
      # may wish to make the data available for all users
      $ sudo mkdir /var/lib/rally_container
      
      # In order for the directory to be accessible by the Rally user
      # (uid: 65500) inside the container, it must be accessible by UID
      # 65500 *outside* the container as well, which is why it is created
      # in ``/var/lib/rally_container``. Creating it in your home directory is
      # only likely to work if your home directory has excessively open
      # permissions (e.g., ``0755``), which is not recommended.
      $ sudo chown 65500 /var/lib/rally_container

      # As opposed to mounting docker image, you must initialize rally database*
      $ docker run -v /var/lib/rally_container:/home/rally/.rally xrally/xrally-openstack:2.0.0 db create

      # And finally, you can start doing your things.*
      $ docker run -v /var/lib/rally_container:/home/rally/.rally xrally/xrally-openstack:2.0.0 env create --name "foo"

Have fun!

# Links

* Free software: Apache license
* Documentation: https://xrally.org
* Source: https://github.com/openstack/rally-openstack
* Bugs: https://bugs.launchpad.net/rally
* Gitter chat: https://gitter.im/xRally/Lobby
