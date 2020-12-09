#!/usr/bin/env python3

import datetime
import json
import subprocess
import re

from ClusterShell import NodeSet

SLURM_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"
TIMESTAMP_FILE = "lasttimestamp"

def main():
    args = ["sacct", "-X", "--allusers", "--parsable2", "--format",
        "jobid,jobidraw,cluster,partition,account,group,gid,"
        "user,uid,submit,eligible,start,end,elapsed,elapsedraw,exitcode,state,nnodes,"
        "ncpus,reqcpus,reqmem,reqgres,reqtres,timelimit,nodelist,jobname",
        "--state",
        "CANCELLED,COMPLETED,FAILED,NODE_FAIL,PREEMPTED,TIMEOUT"]
    # Work out starttime and endtime
    now = datetime.datetime.utcnow()
    end_str = now.strftime(SLURM_DATE_FORMAT)

    try:
        with open(TIMESTAMP_FILE) as f:
            start_str = f.read()
    except FileNotFoundError:
        # Default to last year. It seems that if you specify a time in the distance
        # past then you get no results back.
        last_year = now - datetime.timedelta(days=365)
        start_str = last_year.strftime(SLURM_DATE_FORMAT)

    args += ["--starttime", start_str]
    args += ["--endtime", end_str]

    #print(" ".join(args))
    process = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding="UTF-8")

    # Use the title line to work out the attribute order
    lines = process.stdout.split("\n")
    titles_line = lines[0]
    attributes = titles_line.split("|")

    # Try to output any errors we might have hit
    if len(attributes) < 3:
        print(lines)
        exit(-1)

    # Parse each line of sacct output into a dict
    items = []
    for line in lines[1:]:
      components = line.split("|")
      if len(components) != len(attributes):
          continue

      item = {}
      for i in range(len(attributes)):
          key = attributes[i]
          value = components[i]

          # Try to convert to int
          if "JobID" not in key:
              try:
                  value = int(value)
              except:
                  pass
          item[key] = value

      # Unpack NodeList format, so its easier to search for hostnames
      nodelist = item.get("NodeList")
      if nodelist:
          nodeset = NodeSet.NodeSet(nodelist)
          nodes = list([x for x in nodeset])
          item["AllNodes"] = nodes
          # Produce a prometheus style regex
          nodes_regex = "|".join([re.escape(x) for x in nodes])
          item["AllNodesRegex"] = nodes_regex

      start = item.get("Start")
      if start:
          item["StartEpoch"] = int(datetime.datetime.strptime(start, SLURM_DATE_FORMAT).timestamp() * 1000)

      end = item.get("End")
      if end:
          item["EndEpoch"] = int(datetime.datetime.strptime(end, SLURM_DATE_FORMAT).timestamp() * 1000)

      # Exclude job steps
      jobid = item.get("JobID")
      if jobid and "." not in jobid:
          items.append(item)
          print(json.dumps(item))

    # Write out timestamp, so we know where to start next time
    next = now + datetime.timedelta(seconds=1)
    next_str = next.strftime(SLURM_DATE_FORMAT)
    with open(TIMESTAMP_FILE, 'w') as f:
       f.write(next_str)

    #print(len(items))

    # Do a per node summary of job ids
    # TODO: arguments to toggle this output
    import collections
    node_jobs = collections.defaultdict(list)
    jobs = {}
    for job in items:
        jobs[job["JobID"]] = job
        for node in job["AllNodes"]:
            node_jobs[node] += [{
              "id": job["JobID"],
              "start": job["Start"],
              "end": job["End"],
            }]

    #print(jobs)
    node_info = {
      "node_info": dict(node_jobs),
      "start": start_str,
      "end": end_str,
    }
    #if node_info["node_info"]:
    #    print(node_info)

if __name__ == "__main__":
  main()

