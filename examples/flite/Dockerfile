# our local base image
FROM ubuntu:latest
VOLUME /golem/work /golem/output /golem/resource
ENV DEBIAN_FRONTEND noninteractive
LABEL description="Golem flite tool container" 

RUN apt-get update && \
	apt-get install -y \
		wget \
		g++ \
		make \
		ffmpeg && \
	apt-get -y autoremove && \
	rm -rf /var/lib/apt/lists/*

RUN wget http://www.festvox.org/flite/packed/flite-2.0/flite-2.0.0-release.tar.bz2
RUN tar -xvf flite-2.0.0-release.tar.bz2
RUN cd flite-2.0.0-release && ./configure && make && make install

# docker run --name test -it sylar217/golem-flite:latest
