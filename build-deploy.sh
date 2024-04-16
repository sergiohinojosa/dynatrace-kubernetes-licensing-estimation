#!/bin/bash

 docker build --tag shinojosa/k8stimator:0.2 . 

 docker image push shinojosa/k8stimator:0.2

kubectl set image deployment/my-deployment mycontainer=myimage:1.9.1
