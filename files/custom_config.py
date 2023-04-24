import os
import kubernetes_asyncio as kube
import re


def cpu_count_parser(cpu_count):
    try:
        return int(cpu_count)
    except ValueError:
        if cpu_count.endswith("m"):
            return int(cpu_count[:-1]) / 1000
        else:
            raise ValueError(f"Invalid CPU count: {cpu_count}")


def memory_parser(memory):
    try:
        return int(memory) / 1024**3
    except ValueError:
        if memory.endswith("Mi"):
            return int(memory[:-2]) / 1024
        elif memory.endswith("Ki"):
            return int(memory[:-2]) / 1024**2
        elif memory.endswith("M"):
            return int(memory[:-1]) / 1000
        elif memory.endswith("G"):
            return int(memory[:-1])
        else:
            raise ValueError(f"Invalid memory: {memory}")


async def get_available_resources():
    try:
        if "KUBERNETES_SERVICE_HOST" in os.environ:
            kube.config.load_incluster_config()
        else:
            kube.config.load_kube_config()

        api_instance = kube.client.CoreV1Api()

        nodes = await api_instance.list_node()
        pods = await api_instance.list_pod_for_all_namespaces()

        node_resources = {}

        for node in nodes.items:
            node_name = node.metadata.name
            allocatable = node.status.allocatable
            allocatable_gpus = int(allocatable.get("nvidia.com/gpu", 0))
            allocatable_cpu = cpu_count_parser(allocatable.get("cpu", 0))
            allocatable_memory = memory_parser(allocatable.get("memory", 0))

            node_resources[node_name] = {
                "allocatable_gpus": allocatable_gpus,
                "allocatable_cpu": allocatable_cpu,
                "allocatable_memory": allocatable_memory,
                "allocated_gpus": 0,
                "allocated_cpu": 0,
                "allocated_memory": 0,
            }

        for pod in pods.items:
            node_name = pod.spec.node_name
            if not node_name or node_name not in node_resources:
                continue

            for container in pod.spec.containers:
                if container.resources:
                    if container.resources.requests:
                        node_resources[node_name]["allocated_gpus"] += int(
                            container.resources.requests.get("nvidia.com/gpu", 0)
                        )
                        node_resources[node_name]["allocated_cpu"] += cpu_count_parser(
                            container.resources.requests.get("cpu", 0)
                        )
                        node_resources[node_name]["allocated_memory"] += memory_parser(
                            container.resources.requests.get("memory", 0)
                        )

        await api_instance.api_client.close()
    except Exception as e:
        raise e

    return node_resources


async def available_resources():
    available_resources_form = """
        <!-- Begin "Available resources" section -->
        <div class="row text-center">
            <h4>Available Resources</h4>
        </div>
        <table class="table table-striped table-bordered table-hover">
            <thead class="table-dark">
                <tr>
                    <th class="align-middle">Node</th>
                    <th class="align-middle">Available GPUs</th>
                    <th class="align-middle">Available CPU</th>
                    <th class="align-middle">Available Memory (GB)</th>
                </tr>
            </thead>
            <tbody>
    """

    max_available_gpus = 0
    total_available_gpus = 0

    node_resources = await get_available_resources()
    for node_name, node_resource in node_resources.items():
        row_template = f"""
                <tr>
                    <td class="align-middle">{node_name}</td>
                    <td class="align-middle">{node_resource["allocatable_gpus"] - node_resource["allocated_gpus"]}</td>
                    <td class="align-middle">{round(node_resource["allocatable_cpu"] - node_resource["allocated_cpu"],2)}</td>
                    <td class="align-middle">{round(node_resource["allocatable_memory"] - node_resource["allocated_memory"],2)}</td>
                </tr>
        """
        available_resources_form += row_template
        available_gpus = (
            node_resource["allocatable_gpus"] - node_resource["allocated_gpus"]
        )
        max_available_gpus = max(max_available_gpus, available_gpus)
        total_available_gpus += available_gpus

    available_resources_form += """
            </tbody>
        </table>
        <!-- End "Available resources" section -->
    """
    return available_resources_form, max_available_gpus, total_available_gpus


async def custom_options_form(spawner):
    # max_available_gpus, total_available_gpus = await get_max_available_gpus()
    (
        available_resources_form,
        max_available_gpus,
        total_available_gpus,
    ) = await available_resources()

    user = spawner.user
    is_power_user = set(user.groups).intersection({"admin", "power"})
    print(user.groups)

    cpu_profile_options = {
        f"cpu-{i}": {
            "display_name": f"{i} CPUs",
            "kubespawner_override": {
                "cpu_limit": i,
                "cpu_guarantee": i - 2 if i > 8 else round(i * 0.875),
            },
        }
        # for i in [4,8,16,24,48]
        for i in [4, 6, 12]
    }

    memory_profile_options = {
        f"ram-{i}G": {
            "display_name": f"{i} GB",
            "kubespawner_override": {
                "mem_limit": f"{i}G",
                "mem_guarantee": f"{i-4}G",
            },
        }
        # for i in [16,32,64,128]
        for i in [16, 32, 64]
    }

    gpu_profile_options = {
        f"gpu-{i}": {
            "display_name": f"{i} GPUs",
            "kubespawner_override": {
                "extra_resource_guarantees": {"nvidia.com/gpu": str(i)},
                "extra_resource_limits": {"nvidia.com/gpu": str(i)},
            },
        }
        for i in range(2)
    }

    gpu_image_profile_options = {
        "gpu-jupyter": {
            "display_name": "GPU Jupyter (cschranz/gpu-jupyter:v1.5_cuda-11.6_ubuntu-20.04_python-only)",
            "kubespawner_override": {
                "image": "cschranz/gpu-jupyter:v1.5_cuda-11.6_ubuntu-20.04_python-only",
            },
            "default": True,
        },
        "jupyter-tensorflow": {
            "display_name": "Jupyter Tensorflow (jupyter/tensorflow-notebook:latest)",
            "kubespawner_override": {
                "image": "jupyter/tensorflow-notebook:latest",
            },
        },
        "jupyter-pyspark": {
            "display_name": "Jupyter PySpark (jupyter/pyspark-notebook:latest)",
            "kubespawner_override": {
                "image": "jupyter/pyspark-notebook:latest",
            },
        },
    }

    if is_power_user:
        gpu_profile_options = {
            f"gpu-{i}": {
                "display_name": f"{i} GPUs",
                "kubespawner_override": {
                    "extra_resource_guarantees": {"nvidia.com/gpu": str(i)},
                    "extra_resource_limits": {"nvidia.com/gpu": str(i)},
                },
            }
            for i in range(max_available_gpus + 1)
        }

    else:
        power_cpu = list(cpu_profile_options)[-1]
        cpu_profile_options.pop(power_cpu)
        power_memory = list(memory_profile_options)[-1]
        memory_profile_options.pop(power_memory)

    profile_list = [
        {
            "display_name": "NETS Default Environment",
            "slug": "nets-default",
            "description": "Default environment for NETS users, with 8 CPUs, 32 GB RAM",
            "kubespawner_override": {
                "cpu_limit": 8,
                "cpu_guarantee": 7,
                "mem_limit": "32G",
                "mem_guarantee": "28G",
            },
            "default": True,
        }
    ]

    if total_available_gpus > 0:
        profile_list.append(
            {
                "display_name": "NETS Default Environment (GPU)",
                "slug": "nets-default-gpu",
                "description": "Default environment for NETS users with GPUs, with 8 CPUs, 32 GB RAM, 1 GPU",
                "kubespawner_override": {
                    "cpu_limit": 8,
                    "cpu_guarantee": 7,
                    "mem_limit": "32G",
                    "mem_guarantee": "28G",
                    "extra_resource_guarantees": {"nvidia.com/gpu": "1"},
                    "extra_resource_limits": {"nvidia.com/gpu": "1"},
                    "image": "cschranz/gpu-jupyter:v1.5_cuda-11.6_ubuntu-20.04_python-only",
                },
                "default": True,
            }
        )
        profile_list[0]["default"] = False

    profile_list += [
        {
            "display_name": "Custom Environment",
            "slug": "custom",
            "description": "Create a custom environment with the resources you need.",
            "kubespawner_override": {
                "cpu_guarantee": 2,
                "mem_guarantee": "4G",
            },
            "profile_options": {
                "cpu": {
                    "display_name": "CPUs",
                    "choices": cpu_profile_options,
                },
                "gpu": {
                    "display_name": "GPUs",
                    "choices": gpu_profile_options,
                },
                "memory": {
                    "display_name": "RAM Memory",
                    "choices": memory_profile_options,
                },
                "image": {
                    "display_name": "Docker Image",
                    "choices": gpu_image_profile_options,
                },
            },
        }
    ]
    spawner.profile_list = profile_list
    profile_form_template = spawner.profile_form_template
    # remove existing table in profile_form_template wrapped by "        <!-- Begin "Available resources" section -->" and "        <!-- End "Available resources" section -->"
    profile_form_template = re.sub(
        r"        <!-- Begin \"Available resources\" section -->.*        <!-- End \"Available resources\" section -->",
        "",
        profile_form_template,
        flags=re.DOTALL,
    )
    spawner.profile_form_template = available_resources_form + profile_form_template
    return spawner._options_form_default()
