import click

import mlflow
import mlflow.keras
import mlflow.spark
import numpy as np
import pandas as pd


@click.command()
@click.argument("training_data")
def preprocess(training_data):
    print(training_data)


if __name__ == '__main__':
    preprocess()
