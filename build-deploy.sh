#!/bin/bash

 docker build --tag shinojosa/k8stimator:0.3 . 

 docker image push shinojosa/k8stimator:0.3

kubectl set image deployment/k8stimator k8stimator=shinojosa/k8stimator:0.3 -n k8stimator
