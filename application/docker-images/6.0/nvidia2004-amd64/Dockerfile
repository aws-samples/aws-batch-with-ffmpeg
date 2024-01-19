# ffmpeg - http://ffmpeg.org/download.html
#
# From https://trac.ffmpeg.org/wiki/CompilationGuide/Ubuntu
#
# https://hub.docker.com/r/jrottenberg/ffmpeg/
#
# From https://github.com/jrottenberg/ffmpeg/
#
# Guillaume Marchand - AWS - gmarchan@amazon.fr
#

# Development
FROM        nvidia/cuda:12.3.1-devel-ubuntu20.04 AS devel-base

ENV	    NVIDIA_DRIVER_CAPABILITIES compute,utility,video
ENV	    DEBIAN_FRONTEND=noninteractive
WORKDIR     /tmp/workdir

RUN     apt-get -yqq update && \
        apt-get -yqq upgrade && \
        apt-get install -yqq --no-install-recommends ca-certificates expat libgomp1 software-properties-common libxcb-shape0-dev && \
        apt-get autoremove -y && \
        apt-get clean -y && \
        rm -rf /var/lib/apt/lists/*

# Install Python 3
ARG PYTHON_VERSION=3.11
RUN add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get install -yqq --fix-missing --no-install-recommends curl python${PYTHON_VERSION} python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-distutils python${PYTHON_VERSION}-venv python-is-python3 \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION} \
    && python${PYTHON_VERSION} -m pip install --quiet --no-cache-dir --upgrade pip \
    && update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

# Runtime
FROM        nvidia/cuda:12.3.1-runtime-ubuntu20.04 AS runtime-base

ENV	    NVIDIA_DRIVER_CAPABILITIES compute,utility,video
ENV	    DEBIAN_FRONTEND=noninteractive
WORKDIR     /tmp/workdir

RUN     apt-get -yqq update && \
        apt-get -yqq upgrade && \
        apt-get install -yqq --no-install-recommends ca-certificates expat libgomp1 software-properties-common libxcb-shape0-dev && \
        apt-get autoremove -y && \
        apt-get clean -y && \
        rm -rf /var/lib/apt/lists/*

# Install Python 3
ARG PYTHON_VERSION=3.11
RUN add-apt-repository ppa:deadsnakes/ppa -y \
    && apt-get install -yqq --fix-missing --no-install-recommends curl python${PYTHON_VERSION} python${PYTHON_VERSION}-dev python${PYTHON_VERSION}-distutils python${PYTHON_VERSION}-venv python-is-python3 \
    && apt-get clean -y \
    && rm -rf /var/lib/apt/lists/* \
    && curl -sS https://bootstrap.pypa.io/get-pip.py | python${PYTHON_VERSION} \
    && python${PYTHON_VERSION} -m pip install --quiet --no-cache-dir --upgrade pip \
    && update-alternatives --install /usr/bin/python python /usr/bin/python${PYTHON_VERSION} 1 \
    && update-alternatives --install /usr/bin/python3 python3 /usr/bin/python${PYTHON_VERSION} 1

# Build
FROM devel-base as build

ENV     FFMPEG_VERSION=snapshot \
        NVIDIA_HEADERS_VERSION=12.1.14.0 \
        AOM_VERSION=3.7.0 \
        FDKAAC_VERSION=2.0.2 \
        FONTCONFIG_VERSION=2.14.2 \
        FREETYPE_VERSION=2.10.4 \
        FRIBIDI_VERSION=0.19.7 \
        KVAZAAR_VERSION=2.2.0 \
        LAME_VERSION=3.100 \
        LIBASS_VERSION=0.13.7 \
        OGG_VERSION=1.3.4 \
        OPENCOREAMR_VERSION=0.1.6 \
        OPUS_VERSION=1.4 \
        OPENJPEG_VERSION=2.5.0 \
        THEORA_VERSION=1.1.1 \
        VORBIS_VERSION=1.3.7 \
        VPX_VERSION=1.13.1 \
        WEBP_VERSION=1.3.2 \
        #X264_VERSION=20170226-2245-stable \
        X265_VERSION=3.4 \
        XVID_VERSION=1.3.7 \
        LIBARIBB24_VERSION=1.0.3 \
        LIBPNG_VERSION=1.6.40 \
        LIBVMAF_VERSION=2.3.1 \
        HARFBUZZ_VERSION=8.2.1 \
        SRC=/usr/local

ARG         LD_LIBRARY_PATH=/opt/ffmpeg/lib
ARG         MAKEFLAGS="-j2"
ARG         PKG_CONFIG_PATH="/opt/ffmpeg/share/pkgconfig:/opt/ffmpeg/lib/pkgconfig:/opt/ffmpeg/lib64/pkgconfig"
ARG         PREFIX=/opt/ffmpeg
ARG         LD_LIBRARY_PATH="/opt/ffmpeg/lib:/opt/ffmpeg/lib64"

ARG DEBIAN_FRONTEND=noninteractive

# Dependencies
RUN      buildDeps="autoconf \
        automake \
        cmake \
        curl \
        bzip2 \
        libexpat1-dev \
        g++ \
        gcc \
        git \
        gperf \
        libtool \
        make \
        xz-utils \
        nasm \
        perl \
        pkg-config \
        ninja-build \
        libssl-dev \
        yasm \
        zlib1g-dev" && \
        apt-get -yqq update && \
        apt-get install -yqq --no-install-recommends ${buildDeps} && \
        pip3 install --quiet --no-cache-dir meson

RUN echo "## https://docs.nvidia.com/video-technologies/video-codec-sdk/12.1/ffmpeg-with-nvidia-gpu/index.html#compiling-for-linux"
RUN \
        DIR=/tmp/nv-codec-headers && \
        git clone https://git.videolan.org/git/ffmpeg/nv-codec-headers.git ${DIR} && \
        cd ${DIR} && \
        #git checkout n${NVIDIA_HEADERS_VERSION} && \
        make PREFIX="${PREFIX}" && \
        make install PREFIX="${PREFIX}" && \
        rm -rf ${DIR}
RUN echo "## libvmaf https://github.com/Netflix/vmaf"
RUN \
        DIR=/tmp/vmaf && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/Netflix/vmaf/archive/v${LIBVMAF_VERSION}.tar.gz && \
        tar -xz --strip-components=1 -f v${LIBVMAF_VERSION}.tar.gz && \
        cd /tmp/vmaf/libvmaf && \
        meson build --buildtype release --prefix=${PREFIX} && \
        ninja -vC build && \
        ninja -vC build install && \
        mkdir -p ${PREFIX}/share/model/ && \
        cp -r /tmp/vmaf/model/* ${PREFIX}/share/model/ && \
        rm -rf ${DIR}
RUN echo "## opencore-amr https://sourceforge.net/projects/opencore-amr/"
RUN \
        DIR=/tmp/opencore-amr && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://sourceforge.net/projects/opencore-amr/files/opencore-amr/opencore-amr-${OPENCOREAMR_VERSION}.tar.gz/download | \
        tar -zx --strip-components=1 && \
        ./configure --prefix="${PREFIX}" --enable-shared  && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## x264 http://www.videolan.org/developers/x264.html"
RUN \
        DIR=/tmp/x264 && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        git clone --branch stable https://code.videolan.org/videolan/x264.git ${DIR} && \
        ./configure --prefix="${PREFIX}" --enable-shared --enable-pic --disable-cli && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## x265 http://x265.org/"
RUN \
        DIR=/tmp/x265 && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://github.com/videolan/x265/archive/refs/tags/${X265_VERSION}.tar.gz | \
        tar -zx && \
        cd x265-${X265_VERSION}/build/linux && \
        sed -i "/-DEXTRA_LIB/ s/$/ -DCMAKE_INSTALL_PREFIX=\${PREFIX}/" multilib.sh && \
        sed -i "/^cmake/ s/$/ -DENABLE_CLI=OFF/" multilib.sh && \
        ./multilib.sh && \
        make -C 8bit install && \
        rm -rf ${DIR}
RUN echo "## libogg https://www.xiph.org/ogg/"
RUN \
        DIR=/tmp/ogg && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO http://downloads.xiph.org/releases/ogg/libogg-${OGG_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f libogg-${OGG_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --enable-shared  && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libopus https://www.opus-codec.org/"
RUN \
        DIR=/tmp/opus && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://downloads.xiph.org/releases/opus/opus-${OPUS_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f opus-${OPUS_VERSION}.tar.gz && \
        autoreconf -fiv && \
        ./configure --prefix="${PREFIX}" --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libvorbis https://xiph.org/vorbis/"
RUN \
        DIR=/tmp/vorbis && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO http://downloads.xiph.org/releases/vorbis/libvorbis-${VORBIS_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f libvorbis-${VORBIS_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --with-ogg="${PREFIX}" --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libtheora http://www.theora.org/"
RUN \
        DIR=/tmp/theora && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO http://downloads.xiph.org/releases/theora/libtheora-${THEORA_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f libtheora-${THEORA_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --with-ogg="${PREFIX}" --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libvpx https://www.webmproject.org/code/"
RUN \
        DIR=/tmp/vpx && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://codeload.github.com/webmproject/libvpx/tar.gz/v${VPX_VERSION} | \
        tar -zx --strip-components=1 && \
        ./configure --prefix="${PREFIX}" --enable-vp8 --enable-vp9 --enable-vp9-highbitdepth --enable-pic --enable-shared \
        --disable-debug --disable-examples --disable-docs --disable-install-bins && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libwebp https://developers.google.com/speed/webp/"
RUN \
        DIR=/tmp/vebp && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://storage.googleapis.com/downloads.webmproject.org/releases/webp/libwebp-${WEBP_VERSION}.tar.gz | \
        tar -zx --strip-components=1 && \
        ./configure --prefix="${PREFIX}" --enable-shared  && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libmp3lame http://lame.sourceforge.net/"
RUN \
        DIR=/tmp/lame && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://sourceforge.net/projects/lame/files/lame/${LAME_VERSION}/lame-${LAME_VERSION}.tar.gz/download | \
        tar -zx --strip-components=1 && \
        ./configure --prefix="${PREFIX}" --bindir="${PREFIX}/bin" --enable-shared --enable-nasm --disable-frontend && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## xvid https://www.xvid.com/"
RUN \
        DIR=/tmp/xvid && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://downloads.xvid.com/downloads/xvidcore-${XVID_VERSION}.tar.gz && \
        tar -zx -f xvidcore-${XVID_VERSION}.tar.gz && \
        cd xvidcore/build/generic && \
        ./configure --prefix="${PREFIX}" --bindir="${PREFIX}/bin" && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## fdk-aac https://github.com/mstorsjo/fdk-aac"
RUN \
        DIR=/tmp/fdk-aac && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://github.com/mstorsjo/fdk-aac/archive/v${FDKAAC_VERSION}.tar.gz | \
        tar -zx --strip-components=1 && \
        autoreconf -fiv && \
        ./configure --prefix="${PREFIX}" --enable-shared --datadir="${DIR}" && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## openjpeg https://github.com/uclouvain/openjpeg"
RUN \
        DIR=/tmp/openjpeg && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sL https://github.com/uclouvain/openjpeg/archive/refs/tags/v${OPENJPEG_VERSION}.tar.gz | \
        tar -zx --strip-components=1 && \
        cmake -DBUILD_THIRDPARTY:BOOL=ON -DCMAKE_INSTALL_PREFIX="${PREFIX}" . && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## freetype https://www.freetype.org/ (used by libass)"
RUN  \
        DIR=/tmp/freetype && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://download.savannah.gnu.org/releases/freetype/freetype-${FREETYPE_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f freetype-${FREETYPE_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --disable-static --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## harfbuzz https://github.com/harfbuzz/harfbuzz/ (used by libass)"
RUN  \
        DIR=/tmp/harfbuzz && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/harfbuzz/harfbuzz/releases/download/${HARFBUZZ_VERSION}/harfbuzz-${HARFBUZZ_VERSION}.tar.xz && \
        tar -xf harfbuzz-${HARFBUZZ_VERSION}.tar.xz && \
        cd harfbuzz-${HARFBUZZ_VERSION} && \
        meson build --buildtype=release --prefix=${PREFIX} && \
        meson compile -C build && \
        ninja -C build && \
        ninja install -C build && \
        rm -rf ${DIR}
RUN echo "## fribidi https://www.fribidi.org/ (used by libass)"
RUN  \
        DIR=/tmp/fribidi && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/fribidi/fribidi/archive/${FRIBIDI_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f ${FRIBIDI_VERSION}.tar.gz && \
        sed -i 's/^SUBDIRS =.*/SUBDIRS=gen.tab charset lib bin/' Makefile.am && \
        ./bootstrap --no-config --auto && \
        ./configure --prefix="${PREFIX}" --disable-static --enable-shared && \
        make -j1 && \
        make install && \
        rm -rf ${DIR}
RUN echo "## fontconfig https://www.freedesktop.org/wiki/Software/fontconfig/"
RUN  \
        DIR=/tmp/fontconfig && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://www.freedesktop.org/software/fontconfig/release/fontconfig-${FONTCONFIG_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f fontconfig-${FONTCONFIG_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --disable-static --enable-shared --build=aarch64-unknown-linux-gnu && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libass https://github.com/libass/libass"
RUN  \
        DIR=/tmp/libass && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/libass/libass/releases/download/${LIBASS_VERSION}/libass-${LIBASS_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f libass-${LIBASS_VERSION}.tar.gz && \
        ./configure --prefix="${PREFIX}" --disable-static --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## kvazaar https://github.com/ultravideo/kvazaar"
RUN \
        DIR=/tmp/kvazaar && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/ultravideo/kvazaar/archive/v${KVAZAAR_VERSION}.tar.gz && \
        tar -zx --strip-components=1 -f v${KVAZAAR_VERSION}.tar.gz && \
        ./autogen.sh && \
        ./configure --prefix="${PREFIX}" --disable-static --enable-shared && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## av1 https://aomedia.googlesource.com/aom"
RUN \
        DIR=/tmp/aom && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        git clone --branch v${AOM_VERSION} --depth 1 https://aomedia.googlesource.com/aom ${DIR} && \
        rm -rf CMakeCache.txt CMakeFiles ; \
        mkdir -p ./aom_build ; \
        cd ./aom_build ; \
        cmake -DCMAKE_INSTALL_PREFIX="${PREFIX}" -DBUILD_SHARED_LIBS=1 .. && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libpng http://www.libpng.org/pub/png/libpng.html"
RUN \
        DIR=/tmp/png && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        git clone https://git.code.sf.net/p/libpng/code ${DIR} -b v${LIBPNG_VERSION} --depth 1 && \
        ./configure --prefix="${PREFIX}" && \
        make check && \
        make install && \
        rm -rf ${DIR}
RUN echo "## libaribb24"
RUN \
        DIR=/tmp/b24 && \
        mkdir -p ${DIR} && \
        cd ${DIR} && \
        curl -sLO https://github.com/nkoriyama/aribb24/archive/v${LIBARIBB24_VERSION}.tar.gz && \
        tar -xz --strip-components=1 -f v${LIBARIBB24_VERSION}.tar.gz && \
        autoreconf -fiv && \
        ./configure CFLAGS="-I${PREFIX}/include -fPIC" --prefix="${PREFIX}" && \
        make && \
        make install && \
        rm -rf ${DIR}
RUN echo "## Download ffmpeg https://ffmpeg.org/"
RUN  \
        DIR=/tmp/ffmpeg && mkdir -p ${DIR} && cd ${DIR} && \
        curl -sLO https://ffmpeg.org/releases/ffmpeg-${FFMPEG_VERSION}.tar.bz2 && \
        tar -jx --strip-components=1 -f ffmpeg-${FFMPEG_VERSION}.tar.bz2 && \
        ./configure \
        --disable-debug \
        --disable-doc \
        --disable-ffplay \
        --enable-cuda \
        --enable-cuda-nvcc \
        --enable-cuvid \
        --enable-libnpp \
        --enable-nvenc \
        --enable-fontconfig \
        --enable-gpl \
        --enable-libaom \
        --enable-libaribb24 \
        --enable-libass \
        --enable-libfdk_aac \
        --enable-libfreetype \
        #--enable-libharfbuzz \
        --enable-libfribidi \
        --enable-libfontconfig \
        --enable-libkvazaar \
        --enable-libmp3lame \
        --enable-libopencore-amrnb \
        --enable-libopencore-amrwb \
        --enable-libopenjpeg \
        --enable-libopus \
        --enable-libtheora \
        #--enable-libvmaf \
        --enable-libvorbis \
        --enable-libvpx \
        --enable-libwebp \
        --enable-libx264 \
        --enable-libx265 \
        --enable-nonfree \
        --enable-openssl \
        --enable-postproc \
        --enable-shared \
        --enable-small \
        --enable-version3 \
        --disable-static \
        --extra-cflags="-I${PREFIX}/include -I${PREFIX}/include/ffnvcodec -I/usr/local/cuda/include/" \
        --extra-ldflags="-L${PREFIX}/lib -L/usr/local/cuda/lib64 -L/usr/local/cuda/lib32/" \
        --extra-libs=-ldl \
        --extra-libs=-lpthread \
        --prefix="${PREFIX}" && \
        make clean && \
        make && \
        make install && \
        make distclean && \
        hash -r && \
        cd tools && \
        make qt-faststart && cp qt-faststart ${PREFIX}/bin/

RUN echo "## cleanup"
RUN \
        LD_LIBRARY_PATH="${PREFIX}/lib:${PREFIX}/lib64:${LD_LIBRARY_PATH}" ldd ${PREFIX}/bin/ffmpeg | grep opt/ffmpeg | cut -d ' ' -f 3 | xargs -i cp {} /usr/local/lib/ && \
        for lib in /usr/local/lib/*.so.*; do ln -s "${lib##*/}" "${lib%%.so.*}".so; done && \
        cp ${PREFIX}/bin/* /usr/local/bin/ && \
        cp -r ${PREFIX}/share/* /usr/local/share/ && \
        LD_LIBRARY_PATH=/usr/local/lib ffmpeg -buildconf && \
        cp -r ${PREFIX}/include/libav* ${PREFIX}/include/libpostproc ${PREFIX}/include/libsw* /usr/local/include && \
        mkdir -p /usr/local/lib/pkgconfig && \
        for pc in ${PREFIX}/lib/pkgconfig/libav*.pc ${PREFIX}/lib/pkgconfig/libpostproc.pc ${PREFIX}/lib/pkgconfig/libsw*.pc; do \
        sed "s:${PREFIX}:/usr/local:g; s:/lib64:/lib:g" <"$pc" >/usr/local/lib/pkgconfig/"${pc##*/}"; \
        done

FROM        runtime-base AS release

ENV         LD_LIBRARY_PATH=/usr/local/lib:/usr/local/lib64

# copy only needed files, without copying nvidia dev files
COPY --from=build /usr/local/bin /usr/local/bin/
COPY --from=build /usr/local/share /usr/local/share/
COPY --from=build /usr/local/lib /usr/local/lib/
COPY --from=build /usr/local/include /usr/local/include/

WORKDIR /opt/aws-batch-ffmpeg/batch
COPY DroidSansMono.ttf ffmpeg_wrapper.py requirements.txt ./
COPY aws aws/

# Install fonts
RUN mkdir -p /usr/share/fonts/truetype/ && \
        mv DroidSansMono.ttf /usr/share/fonts/truetype/ && \
        fc-cache -fv

RUN pip3 install --quiet --no-cache-dir -r requirements.txt

CMD ["--help"]
ENTRYPOINT  ["python3", "ffmpeg_wrapper.py"]
