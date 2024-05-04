#!/bin/bash

name="k8stimator"
version=0.17
image="shinojosa/$name:$version"

deployment=$name
container=$image
ns=$name

docker build --tag $image . 

docker image push $image

kubectl set image deployment/$deployment $name=$container -n $ns
