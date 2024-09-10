FROM python:3.7-slim 
WORKDIR /work
COPY . /work

COPY sources.list /etc/apt/sources.list.d/debian.sources

RUN apt-get update
RUn apt-get install -y curl 

RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r requirements.txt 
CMD ["python", "start.py"]