#!/usr/bin/env python3

import os
import pwd
import grp
import re
import sys
import shutil


def chown(path: str, owner: str, group: str, **kwargs) -> None:
    """Change ownership of a file or directory given an username and a group name."""
    uid = pwd.getpwnam(owner).pw_uid
    gid = grp.getgrnam(group).gr_gid
    os.chown(path, uid, gid, **kwargs)


# Certbot sets an environment variable RENEWED_LINEAGE, which points to the
# path of the renewed certificate. We use that path to determine and find
# the files for the currently renewed certificated
lineage = os.environ.get("RENEWED_LINEAGE")

# If nothing renewed, exit
if not lineage:
    sys.exit()

# From the linage, we strip the 'domain name', which is the last part
# of the path.
result = re.match(r".*/live/(.+)$", lineage)

# If we can not recognize the path, we exit with 1
if not result:
    sys.exit(1)

# Extract the domain name
domain = result.group(1)

# Define a path for stalwart where you want to write the .pem file.
deploy_cert_path = "/etc/ssl/stalwart/" + domain + ".pem"
deploy_key_path = "/etc/ssl/stalwart/" + domain + ".key"

# The source files can be found in below paths, constructed with the lineage
# path
source_key_path = lineage + "/privkey.pem"
source_chain_path = lineage + "/fullchain.pem"

shutil.copy2(source_key_path, deploy_key_path)
shutil.copy2(source_chain_path, deploy_cert_path)

chown(deploy_key_path, "stalwart", "stalwart")
chown(deploy_cert_path, "stalwart", "stalwart")

# Here you can add your service reload command. Which will be executed after
# every renewal, which is fine if you only have a few domains.

# Alternative is to add the reload to the --post-hook. In that case it is only
# run once after all renewals. That would be the use-case if you have a large
# number of different certificates served by HAproxy.
