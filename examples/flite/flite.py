#!/usr/bin/env python3
import asyncio
import pathlib
import sys

from yapapi import (
    Executor,
    Task,
    __version__ as yapapi_version,
    WorkContext
)
from yapapi.log import enable_default_logger, log_summary, log_event_repr  # noqa
from yapapi.package import vm
from yapapi.rest.activity import BatchTimeoutError

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
        image_hash="895cd661f729e2b7034c0e19e4adc79830e2a1fd7e7f081b4ce0fb32",
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
            )
            
            ctx.run("/bin/sh", "-c", commands)

            ctx.download_file("/golem/output/log.txt", "log.txt")
            ctx.download_file(f"/golem/output/{output_file}", output_file)

            try:
                # Set timeout for executing the script on the provider. Two minutes is plenty
                # of time for computing a single frame, for other tasks it may be not enough.
                # If the timeout is exceeded, this worker instance will be shut down and all
                # remaining tasks, including the current one, will be computed by other providers.
                yield ctx.commit(timeout=timedelta(minutes=5))
                # TODO: Check if job results are valid
                # and reject by: task.reject_task(reason = 'invalid file')
                task.accept_result(result=output_file)
            except BatchTimeoutError:
                print(
                    f"{utils.TEXT_COLOR_RED}"
                    f"Task timed out: {task}, time: {task.running_time}"
                    f"{utils.TEXT_COLOR_DEFAULT}"
                )
                raise

        ctx.log("task done")

    # iterator over the frame indices that we want to render
    #nodes = [Task(data={'node': i+1, 'nodes': node_count}) for i in range(node_count)]

    init_overhead: timedelta = timedelta(minutes=30)

    # By passing `event_emitter=log_summary()` we enable summary logging.
    # See the documentation of the `yapapi.log` module on how to set
    # the level of detail and format of the logged information.
    async with Executor(
        package=package,
        max_workers=1, #node_count,
        budget=30.0,
        timeout=init_overhead, #+ timedelta(minutes=node_count * 2), add something based on content length?
        subnet_tag=subnet_tag,
        event_consumer=log_summary(log_event_repr),
    ) as executor:

        async for task in executor.submit(worker, [Task(data="")]):
            print(
                f"{utils.TEXT_COLOR_CYAN}"
                f"Task computed: {task}, result: {task.output}"
                f"{utils.TEXT_COLOR_DEFAULT}"
            )
        
    # Processing is done, so remind the user of the parameters and show the results
    # TODO - need to decompress the file


if __name__ == "__main__":
    parser = utils.build_parser("Flite converter for Gutenberg books")
    parser.set_defaults(log_file="blender-yapapi.log")
    parser.add_argument("resource_url")
    # parser.add_argument("timeout_seconds")
    # parser.add_argument("password")
    # parser.set_defaults(log_file="john.log", node_count="4", timeout_seconds="10", password="unicorn")
    args = parser.parse_args()

    enable_default_logger(log_file=args.log_file)
    loop = asyncio.get_event_loop()
    subnet = args.subnet_tag
    sys.stderr.write(
        f"yapapi version: {utils.TEXT_COLOR_YELLOW}{yapapi_version}{utils.TEXT_COLOR_DEFAULT}\n"
    )
    sys.stderr.write(f"Using subnet: {utils.TEXT_COLOR_YELLOW}{subnet}{utils.TEXT_COLOR_DEFAULT}\n")
    task = loop.create_task(main(subnet_tag=args.subnet_tag, resource_url=args.resource_url))
    try:
        loop.run_until_complete(task)

    except KeyboardInterrupt:
        print(
            f"{utils.TEXT_COLOR_YELLOW}"
            "Shutting down gracefully, please wait a short while "
            "or press Ctrl+C to exit immediately..."
            f"{utils.TEXT_COLOR_DEFAULT}"
        )
        task.cancel()
        try:
            loop.run_until_complete(task)
            print(
                f"{utils.TEXT_COLOR_YELLOW}"
                "Shutdown completed, thank you for waiting!"
                f"{utils.TEXT_COLOR_DEFAULT}"
            )
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass

