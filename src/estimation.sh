#!/bin/bash
# Simple shell script that assist in the license calculation for
# Kubernetes Clusters. 
#
#


# ----------------------
# Variables declaration and helper 
# functions

NAMESPACES_TO_EXCLUDE="system|dynatrace|cert-manager|istio"
namespaces_msg="
 The following namespaces will be exluded from the Gib/h calculation.
 Modify the 'NAMESPACES_TO_EXCLUDE' variable so the estimation suits your 
 cluster accordingly. Add words to the exclusion list and separate each 
 with a pipe '|'. The exclusion is case insensitive.
 
 NAMESPACES_TO_EXCLUDE=$NAMESPACES_TO_EXCLUDE
 "

# --- Variables --

# List prices $0.002 per POD-hour in USD
price_pod_hour=0.002
# List price  $0.01 per Gib-hour AppOnly in USD
price_gib_hour=0.01

declare -r min_memory=256
declare -a rounded_memories
declare -a actual_memories
declare -i total_pods

# -- functions -- 
timestamp() {
    date +"[%Y-%m-%d %H:%M:%S]"
}

printInfo() {
    echo ""
    echo "     $1"
}

printInfoSection() {
    echo ""
    echo "$thickline"
    echo "$halfline $1 $halfline"
    echo "$thinline"
}

thickline="======================================================================"
halfline="============"
thinline="______________________________________________________________________"
infolog="[License-estimation|INFO] $(timestamp) |"


#
# ---- License estimation logic
#
calculatePodHours() {

    # Calculation of the POD Hours for the Year
    printInfoSection "POD Hours Calculation"

    total_pods=$(kubectl get pods --all-namespaces | wc -l)
    # Command 1: This wil help to estimate the average # of pods running per day
    printInfo "SUM of PODs in the Cluster: $total_pods"

    printInfo "Assuming these $total_pods pods run for 24 hours and 365 days"
    printInfo "The yearly pod-hour consumption is $((total_pods * 24 * 365)) pod-hours"
    
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

    echo "$namespaces_msg"
    # Snapshot of actual PODs with their Utilization
    pods_top=$(kubectl top pods --all-namespaces --no-headers | grep -viE $NAMESPACES_TO_EXCLUDE )

    # See comments in 'done' to understand the process substitution
    while read -r line; do
        # We extract the Memory in Mi
        mem=$(echo "$line" | awk '{print($4)}')
        # We extract only the integer
        m=$(echo "$mem" | tr -dc '0-9')
        if ((m < min_memory)); then
            m_rounded=$min_memory
        else
            a=$((m / min_memory))

            m_rounded=$((a * min_memory))

            # If we have remainders we increase to next round up
            if [[ $((m % min_memory)) -gt 0 ]]; then
                m_rounded=$((m_rounded + min_memory))
            fi
        fi

        #echo "adding to array ${memories[*]} $m_rounded from pos $i"
        # save value to array
        rounded_memories[i]=$m_rounded
        actual_memories[i]=$m
        # We round up to 256
        #echo "$i|$line rounded to $m_rounded Mi"
        ((i++))

    # We read the output using process substitution to save the results in an array within the same process 
    # otherwise the array endsup empty after the while loop
    # Using "Quotes" for preserving Multilines
    done < <(echo "${pods_top}")

    echo "------------"
    echo "Finished rounding up"
    echo ""
}

calculateMemoryYearlyUsage(){
     
    printInfoSection "POD Memory Yearly Usage Estimation"
    
    for k in "${!rounded_memories[@]}"
    do
        total_memory_rounded=$((total_memory_rounded + rounded_memories[k]))
        total_memory_actual=$((total_memory_actual + actual_memories[k]))
    done
    total_memory_rounded=$((total_memory_rounded * 24 ))
    total_memory_actual=$((total_memory_actual * 24 ))

    printInfo "For the ${#rounded_memories[@]} PODs these are the calculations assuming they run 24/7 for 365 days"

    echo "Hourly Total Memory rounded $total_memory_rounded Mi/h"
    echo "Hourly Total Memory actual $total_memory_actual Mi/h"
    echo ""
    echo "Yearly Total Memory rounded $(( (total_memory_rounded * 24 * 365 ) / 1024 )) GiB/h"
    echo "Yearly Total Memory actual $(( (total_memory_actual * 24 * 365 ) / 1024 )) GiB/h"
}

calculateYearlyConsumption(){

     printInfoSection "GiB-Hour and POD-Hour yearly costs estimation"

     echo ""
     echo "---- POD-hour estimation ---- "
     echo "The price for POD-hour is $ $price_pod_hour USD"
     yearly_pod_hours=$((total_pods * 24 * 365))
     # Using AWK for floating number calculation 
     yearly_pod_hours_est=$(echo $yearly_pod_hours $price_pod_hour | awk '{print $1 * $2}' )
     echo "The price for $yearly_pod_hours yearly pod-hours is: $yearly_pod_hours_est USD"
     echo ""
     
     
     echo ""
     echo "---- GiB-hour estimation ---- "
     echo "The price for GiB-hour is $ $price_gib_hour USD"
     yearly_gib_hours=$(( (total_memory_rounded * 24 * 365 ) / 1024 ))
    
     # Using AWK for floating number calculation 
     yearly_gib_hours_est=$(echo $yearly_gib_hours $price_gib_hour | awk '{print $1 * $2}' )
     echo "The price for $yearly_gib_hours yearly GiB-hours is: $yearly_gib_hours_est USD"
     echo ""

    #TODO: add Classic FullStack Price to compare from the Total Memory of the Cluster?

}


getClusterInfo

calculatePodHours

calculateMemoryRoundUp

calculateMemoryYearlyUsage

calculateYearlyConsumption

