# ffmpeg - http://ffmpeg.org/download.html
#
# From https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu
#
# https://xilinx.github.io/video-sdk/v3.0/container_setup.html#creating-a-docker-image
#
# Guillaume Marchand - AWS - gmarchan@amazon.fr
#
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV TZ=America/New_York

RUN \
        echo 'deb [trusted=yes] https://packages.xilinx.com/artifactory/debian-packages focal main' > /etc/apt/sources.list.d/xilinx.list && \
        echo "Acquire { https::Verify-Peer false }" > ca

# Install Xilinx drivers
RUN \
    apt-get -yqq update && \
    apt-get install -yqq --fix-missing --no-install-recommends git ca-certificates apt-utils software-properties-common openssl libssl-dev wget curl && \
    apt-get install -yqq --fix-missing --no-install-recommends xrt=2.11.722 xilinx-alveo-u30-core xilinx-alveo-u30-examples && \
    apt-mark hold xrt && \
    apt-get autoremove -y && \
    apt-get clean -y && \
    rm -rf /var/lib/apt/lists/*

# Install Python 3
ARG PYTHON_VERSION=3.11
RUN \
    add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get install -yqq --fix-missing --no-install-recommends python${PYTHON_VERSION} python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-distutils python${PYTHON_VERSION}-venv python-is-python3 \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION} \
    && python${PYTHON_VERSION} -m pip install --no-cache-dir --upgrade pip \
    && update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

RUN \
        git clone https://github.com/gdraheim/docker-systemctl-replacement.git /usr/local/share/docker-systemctl-replacement && \
        echo "alias systemctl='python3 /usr/local/share/docker-systemctl-replacement/files/docker/systemctl3.py'" >> /root/.bashrc && \
        ln -s /usr/local/share/docker-systemctl-replacement/files/docker/systemctl3.py /usr/local/bin/systemctl


ENV XILINX_XRT=/opt/xilinx/xrt
ENV XILINX_XRM=/opt/xilinx/xrm
ENV XILINX_VVAS=/opt/xilinx/vvas
ENV PATH=$XILINX_XRM/bin:$XILINX_VVAS/bin:$XILINX_XRT/bin:/opt/xilinx/ffmpeg/bin:/usr/local/bin/:/opt/xilinx/xcdr/bin:/opt/xilinx/launcher/bin:/opt/xilinx/jobSlotReservation/bin:$PATH
ENV LD_LIBRARY_PATH=$XILINX_XRM/lib:$XILINX_VVAS/lib:$XILINX_XRT/lib:/opt/xilinx/ffmpeg/lib:$LD_LIBRARY_PATH
ENV PKG_CONFIG_PATH=$XILINX_VVAS/lib/pkgconfig:$PKG_CONFIG_PATH
ENV PYTHONPATH=$XILINX_XRT/python:$PYTHONPATH

WORKDIR /opt/aws-batch-ffmpeg/batch

COPY wrapper/DroidSansMono.ttf wrapper/wrapper.py requirements.txt ./
COPY shared_libraries/ shared_libraries/
COPY docker-images/4.4/xilinx2004-amd64/entrypoint.sh ./

RUN chmod +x entrypoint.sh

# Install fonts
RUN mkdir -p /usr/share/fonts/truetype/ && \
        mv DroidSansMono.ttf /usr/share/fonts/truetype/ && \
        fc-cache -fv

RUN python${PYTHON_VERSION} -m pip install --no-cache-dir -r requirements.txt


ENTRYPOINT ["./entrypoint.sh"]
CMD ["--help"]
