#!/bin/bash

kubectl create ns k8stimator

kubectl create deployment k8stimator --image=shinojosa/k8stimator:0.1 -n k8stimator

kubectl expose deployment k8stimator --port=80 --target-port=8080 -n k8stimator
