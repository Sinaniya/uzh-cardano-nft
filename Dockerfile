FROM python:3.9-slim

# environment variables
ENV BOOTSTRAP_HASKELL_NONINTERACTIVE=1
ENV BOOTSTRAP_HASKELL_GHC_VERSION=8.10.7
ENV BOOTSTRAP_HASKELL_CABAL_VERSION=3.6.2.0
ENV LD_LIBRARY_PATH="/usr/local/lib:$LD_LIBRARY_PATH"
ENV PKG_CONFIG_PATH="/usr/local/lib/pkgconfig:$PKG_CONFIG_PATH"

# use bash shell
RUN rm /bin/sh && ln -s /bin/bash /bin/sh

# install OS dependencies
RUN apt-get update -y && apt-get upgrade -y
RUN apt-get install automake build-essential pkg-config libffi-dev libgmp-dev libssl-dev libtinfo-dev libsystemd-dev zlib1g-dev make g++ tmux git jq wget curl libncursesw5 libtool autoconf llvm-9 clang-9 libnuma-dev -y \
    && ln -s /usr/bin/llvm-config-9 /usr/bin/llvm-config \
    && ln -s /usr/bin/opt-9 /usr/bin/opt \
    && ln -s /usr/bin/llc-9 /usr/bin/llc \
    && ln -s /usr/bin/clang-9 /usr/bin/clang

# install GHC and Cabal
RUN curl --proto '=https' --tlsv1.2 -sSf https://get-ghcup.haskell.org | sh

WORKDIR $HOME/cardano-src

# install libsodium
RUN git clone https://github.com/input-output-hk/libsodium \
    && cd libsodium \
    && git checkout 66f017f1 \
    && ./autogen.sh \
    && ./configure \
    && make \
    && make install

# install libsecp256k1 
RUN git clone https://github.com/bitcoin-core/secp256k1 \
    && cd secp256k1 \
    && git checkout ac83be33 \
    && ./autogen.sh \
    && ./configure --enable-module-schnorrsig --enable-experimental \
    && make \
    && make install

# install cardano-node and cardano-cli
RUN git clone https://github.com/input-output-hk/cardano-node.git \
    && cd cardano-node \
    && git fetch --all --recurse-submodules --tags \
    && git checkout $(curl -s https://api.github.com/repos/input-output-hk/cardano-node/releases/latest | jq -r .tag_name)
RUN source $HOME/.ghcup/env \
    && cd cardano-node \
    && cabal configure --with-compiler=ghc-8.10.7 \
    && cabal build cardano-node cardano-cli
RUN cd cardano-node \
    && mkdir -p $HOME/.local/bin \
    && cp -p "$(./scripts/bin-path.sh cardano-node)" $HOME/.local/bin/ \
    && cp -p "$(./scripts/bin-path.sh cardano-cli)" $HOME/.local/bin/
RUN echo "PATH=$HOME/.local/bin/:$PATH" >> ~/.bashrc \
    && source ~/.bashrc

# install blockfrost-cardano-cli
RUN curl -sL https://deb.nodesource.com/setup_16.x | bash
RUN apt-get install nodejs -y
RUN npm install -g @blockfrost/blockfrost-cardano-cli
