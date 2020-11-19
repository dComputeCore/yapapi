#!/usr/bin/env python3
import asyncio
import pathlib
import sys

import yapapi
from yapapi.log import enable_default_logger, log_summary, log_event_repr  # noqa
from yapapi.runner import Engine, Task, vm
from yapapi.runner.ctx import WorkContext
from datetime import timedelta
import requests

# For importing `utils.py`:
script_dir = pathlib.Path(__file__).resolve().parent
parent_directory = script_dir.parent
sys.stderr.write(f"Adding {parent_directory} to sys.path.\n")
sys.path.append(str(parent_directory))
import utils  # noqa

async def main(subnet_tag: str, resource_url: str):
    resource_content = requests.get(resource_url)

    print(f"Downloaded resource length: {len(resource_content.content)}")

    open('resource.txt', 'wb').write(resource_content.content)
    

    package = await vm.repo(
        image_hash="1b3a22583c2fa1560b2b192239615233598fb2d31795685fb5036a03",
        min_mem_gib=4,
        min_storage_gib=20.0,
    )

    async def worker(ctx: WorkContext, tasks):
        async for task in tasks:
            output_file = "result.flac"
            ctx.send_file("resource.txt", "/golem/work/resource.txt")

            commands = (
                "cd /golem/output/; " #
                "flite -v /golem/work/resource.txt result.wav > log.txt 2>&1; "
                "ffmpeg -i result.wav result.flac; "
                "ls -lh result* >> log.txt"
            )
            
            ctx.run("/bin/sh", "-c", commands)

            ctx.download_file("/golem/output/log.txt", "log.txt")
            ctx.download_file(f"/golem/output/{output_file}", output_file)
            yield ctx.commit()
            # TODO: Check if job results are valid
            # and reject by: task.reject_task(reason = 'invalid file')
            task.accept_task(result=output_file)

        ctx.log("task done")

    # iterator over the frame indices that we want to render
    #nodes = [Task(data={'node': i+1, 'nodes': node_count}) for i in range(node_count)]

    init_overhead: timedelta = timedelta(minutes=30)

    # By passing `event_emitter=log_summary()` we enable summary logging.
    # See the documentation of the `yapapi.log` module on how to set
    # the level of detail and format of the logged information.
    async with Engine(
        package=package,
        max_workers=1, #node_count,
        budget=100.0,
        timeout=init_overhead, #+ timedelta(minutes=node_count * 2), add something based on content length?
        subnet_tag=subnet_tag,
        event_emitter=log_summary(log_event_repr),
    ) as engine:

        async for task in engine.map(worker, [Task(data="")]):
            print(
                f"{utils.TEXT_COLOR_CYAN}"
                f"Task computed: {task}, result: {task.output}"
                f"{utils.TEXT_COLOR_DEFAULT}"
            )
        
    # Processing is done, so remind the user of the parameters and show the results
    # TODO - need to decompress the file


if __name__ == "__main__":
    parser = utils.build_parser("Flite converter for Gutenberg books")
    parser.add_argument("resource_url")
    # parser.add_argument("timeout_seconds")
    # parser.add_argument("password")
    # parser.set_defaults(log_file="john.log", node_count="4", timeout_seconds="10", password="unicorn")
    args = parser.parse_args()

    enable_default_logger(log_file=args.log_file)
    loop = asyncio.get_event_loop()
    subnet = args.subnet_tag
    sys.stderr.write(
        f"yapapi version: {utils.TEXT_COLOR_YELLOW}{yapapi.__version__}{utils.TEXT_COLOR_DEFAULT}\n"
    )
    sys.stderr.write(f"Using subnet: {utils.TEXT_COLOR_YELLOW}{subnet}{utils.TEXT_COLOR_DEFAULT}\n")
    task = loop.create_task(main(subnet_tag=args.subnet_tag, resource_url=args.resource_url))
    try:
        asyncio.get_event_loop().run_until_complete(task)

    except (Exception, KeyboardInterrupt) as e:
        print(e)
        task.cancel()
        asyncio.get_event_loop().run_until_complete(task)
