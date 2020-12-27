FROM python:3.7
COPY . /app
WORKDIR /app

# You only need this if you need to run make
#ENV NODE_VERSION=10.23.0
#RUN apt install -y curl
#RUN curl -o- https://raw.githubusercontent.com/creationix/nvm/v0.34.0/install.sh | bash
#ENV NVM_DIR=/root/.nvm
#RUN . "$NVM_DIR/nvm.sh" && nvm install ${NODE_VERSION}
#RUN . "$NVM_DIR/nvm.sh" && nvm use ${NODE_VERSION}
#RUN . "$NVM_DIR/nvm.sh" && nvm alias default v${NODE_VERSION}
#ENV PATH="/root/.nvm/versions/node/v${NODE_VERSION}/bin/:${PATH}"
#RUN npm install

RUN pip install -U pip
RUN pip install -r requirements.txt

EXPOSE 9001

ENTRYPOINT ["python", "ascii_telnet_server.py", "run"]
