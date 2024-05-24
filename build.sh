#!/bin/bash

rm -r build/ dist/ OmenEye.egg-info/

pip uninstall OmenEye -y

python3 setup.py sdist bdist_wheel

pip install dist/OmenEye-0.1.0-py3-none-any.whl
