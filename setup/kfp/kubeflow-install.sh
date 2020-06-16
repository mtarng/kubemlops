#!/bin/sh

mkdir -p ~/tmp
mkdir -p ~/tmp/kfctl

# Linux
curl -L https://github.com/kubeflow/kfctl/releases/download/v1.0.2/kfctl_v1.0.2-0-ga476281_linux.tar.gz --output ~/tmp/kfctl/kfctl_v1.0.2-0-ga476281_linux.tar.gz
tar -zxf ~/tmp/kfctl/kfctl_v1.0.2-0-ga476281_linux.tar.gz 
sudo mv kfctl /usr/local/bin/

# Mac OS X
# curl -L https://github.com/kubeflow/kfctl/releases/download/v1.0.2/kfctl_v1.0.2-0-ga476281_darwin.tar.gz | tar -xv -C ~/tmp/kfctl/
# sudo mv ~/tmp/kfctl/kfctl /usr/local/bin/

export BASE_DIR=kfinstall
export KF_NAME=kubeflow
export KF_DIR=${BASE_DIR}/${KF_NAME}
mkdir -p ${KF_DIR}
cp kfctl_k8s_light.yaml ${KF_DIR}/
cd ${KF_DIR}
kfctl apply -V -f kfctl_k8s_light.yaml
