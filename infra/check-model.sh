#!/bin/bash
if test -f /var/lib/schema-model/ready; then
  echo MODEL_READY
  cat /var/lib/schema-model/ready.json
else
  echo MODEL_INSTALL_PENDING
  cloud-init status || true
  if test -f /var/log/schema-model-install.log; then tail -c 1200 /var/log/schema-model-install.log; fi
fi
