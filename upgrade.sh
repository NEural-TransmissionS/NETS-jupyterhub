#!/bin/bash
HELM_RELEASE=jhub
helm upgrade --cleanup-on-fail \
  --install $HELM_RELEASE ./ \
  --namespace $HELM_RELEASE \
  --create-namespace \
  --values config.yaml \
  --values secrets.yaml
  # --dry-run --debug > upgrade.log

