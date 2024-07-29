#!/bin/bash

setVariables() {

    NAME="k8stimator"
    NAMESPACE="k8stimator"

    VERSION=0.42
    IMAGE="shinojosa/$NAME:$VERSION"

    DEPLOYMENT=$NAME
    CONTAINER=$IMAGE
    YAMLFILE=$VERSION-$(date '+%Y-%m-%d_%H_%M_%S').yaml
    export RELEASE_VERSION=$VERSION
    export IMAGE=$IMAGE

}

buildDockerImage() {
    docker build --tag $IMAGE .
}

pushImageToRepository() {

    docker image push $IMAGE

}

createDeployment() {

    envsubst <k8s/deployment.yaml >k8s/gen/deploy-$YAMLFILE

    kubectl apply -f k8s/gen/deploy-$YAMLFILE
    # kubectl set image deployment/$deployment $name=$container -n $ns
}


setVariables
buildDockerImage
pushImageToRepository
createDeployment
