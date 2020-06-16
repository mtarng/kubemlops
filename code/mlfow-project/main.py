
import click
import os
import mlflow
from mlflow.utils import mlflow_tags
from mlflow.entities import RunStatus
from mlflow.utils.logging_utils import eprint


@click.command()
@click.argument("training_data")
def workflow(param_one):
    with mlflow.start_run() as active_run:

        preprocess_run = mlflow.run(".", "preprocess", parameters={
                                    "training_data": training_data})
        train_model_run = mlflow.run(".", "train", parameters={
                                     "training_data": training_data})


if __name__ == '__main__':
    workflow()
