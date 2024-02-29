#!/bin/bash
#
#

# Variables declaration

min_memory=256
declare -gA memories

thickline="======================================================================"
halfline="============"
thinline="______________________________________________________________________"

# FUNCTIONS DECLARATIONS
timestamp() {
    date +"[%Y-%m-%d %H:%M:%S]"
}

printInfo() {
    echo ""
    echo "[License-estimation|INFO] $(timestamp) |----> $1 <----|"
}

printInfoSection() {
    echo ""
    echo "[License-estimation|INFO] $(timestamp) |$thickline"
    echo "[License-estimation|INFO] $(timestamp) |$halfline $1 $halfline"
    echo "[License-estimation|INFO] $(timestamp) |$thinline"
}

printWarn() {
    echo "[License-estimation|WARN] $(timestamp) |----> $1 <----|"
}

printError() {
    echo "[License-estimation|ERROR] $(timestamp) |----> $1 <----|"
}

calculatePodHours() {

    printInfoSection "POD Hours Calculation"
    # Command 1: This wil help to estimate the average # of pods running per day
    printInfo "SUM of PODs: $(kubectl get pods --all-namespaces | wc -l)"
}

getXX() {
    # Command 2: This wil show the # of pods that you might want to instrument for tracing and profiling
    kubectl top pods --all-namespaces --sum=true

    # Command 3: This shows how many Istio data planes pods are running
    kubectl get pod -o "custom-columns=NAME:.metadata.name,INIT:.spec.initContainers[*].name,CONTAINERS:.spec.containers[*].name" --all-namespaces | grep istio-proxy | wc -l
}

getClusterInfo() {
    printInfoSection "Cluster Information"
    printInfo Cluster-Info
    kubectl cluster-info

    printInfo "Nodes Information"
    kubectl get nodes -o wide

    printInfo "Nodes Utilization"
    kubectl top nodes
}

calculateMemoryRoundUp() {
    printInfoSection "POD Memory Calculation"
    i=0

    # Snapshot of actual PODs with their Utilization
    pods_top=$(kubectl top pods --all-namespaces --no-headers)

    # In "Quotes" for preserving Multilines
    echo "${pods_top}" |
        while read -r line; do
            # We extract the Memory in Mi
            mem=$(echo $line | awk '{print($4)}')
            # We extract only the integer
            m=$(echo $mem | tr -dc '0-9')
            if ((m < min_memory)); then
                m_rounded=$min_memory
            else
                a=$((m / min_memory))

                m_rounded=$((a * min_memory))

                # If we have remainders we increase to next round up
                if [[ $((m % min_memory)) > 0 ]]; then
                    m_rounded=$((m_rounded + min_memory))
                fi
            fi
            # save value to array
            echo "adding to array ${memories[*]} $m_rounded from pos $i"

            memories[i]=$m_rounded
            # We round up to 256
            echo "$line rounded to $m_rounded Mi"
            ((i++))
        done
    
    echo "Finish rounding up" 
    echo "${memories[*]}"
    echo "${memories[@]}"
}

calculateMemoryRoundUp
