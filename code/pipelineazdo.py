"KubeFlow Pipeline with AzureDevops Callback"
from kubernetes import client as k8s_client
import kfp.dsl as dsl
import kfp.compiler as compiler
import kfp.components as comp
from kfp.azure import use_azure_secret
from kubernetes.client.models import V1EnvVar


@dsl.pipeline(
    name='Tacos vs. Burritos',
    description='Simple TF CNN'
)
def use_databricks_secret(secret_name='databricks-secret'):
    def _use_databricks_secret(task):
        from kubernetes import client as k8s_client
        (
            task.container
                .add_env_variable(
                    k8s_client.V1EnvVar(
                        name='DATABRICKS_HOST',
                        value_from=k8s_client.V1EnvVarSource(
                            secret_key_ref=k8s_client.V1SecretKeySelector(
                                name=secret_name,
                                key='DATABRICKS_HOST'
                            )
                        )
                    )
                )
                .add_env_variable(  # noqa: E131
                    k8s_client.V1EnvVar(
                        name='DATABRICKS_TOKEN',
                        value_from=k8s_client.V1EnvVarSource(
                            secret_key_ref=k8s_client.V1SecretKeySelector(
                                name=secret_name,
                                key='DATABRICKS_TOKEN'
                            )
                        )
                    )
                )
                .add_env_variable(  # noqa: E131
                    k8s_client.V1EnvVar(
                        name='CLUSTER_ID',
                        value_from=k8s_client.V1EnvVarSource(
                            secret_key_ref=k8s_client.V1SecretKeySelector(
                                name=secret_name,
                                key='CLUSTER_ID'
                            )
                        )
                    )
                )
        )
        return task
    return _use_databricks_secret


def azdocallback(callbackinfo):
    if callbackinfo is not None:
        import sys
        import subprocess
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'])
        import requests                                                                   # noqa: F811,E501
        import json                                                                       # noqa: F811,E501
        callback_vars = json.loads(callbackinfo.replace("'", '"'))  # noqa: E501
        url = r"{planUri}/{projectId}/_apis/distributedtask/hubs/{hubName}/plans/{planId}/events?api-version=2.0-preview.1".format(                           # noqa: E501
            planUri=callback_vars["PlanUri"], projectId=callback_vars["ProjectId"], hubName=callback_vars["HubName"], planId=callback_vars["PlanId"])          # noqa: E501
        data = {'name': 'TaskCompleted',
                'taskId': callback_vars["TaskInstanceId"], 'jobId': callback_vars["JobId"], 'result': 'succeeded'}   # noqa: E501
        header = {'Authorization': 'Bearer ' + callback_vars["AuthToken"]}
        response = requests.post(url, json=data, headers=header)
        print(response)


def tacosandburritos_train(
    resource_group,
    workspace,
    dataset,
    azdocallbackinfo=None
):
    """Pipeline steps"""

    persistent_volume_path = '/mnt/azure'
    data_download = dataset  # noqa: E501
    batch = 32
    model_name = 'tacosandburritos'
    operations = {}
    image_size = 160
    training_folder = 'train'
    training_dataset = 'train.txt'
    model_folder = 'model'
    image_repo_name = "kubeflowyoacr.azurecr.io/mexicanfood"
    mlflow_url = 'http://mlflow:5000'

    exitop = comp.func_to_container_op(azdocallback)
    with dsl.ExitHandler(exit_op=exitop(azdocallbackinfo)):

        operations['data processing on databricks'] = dsl.ContainerOp(
            name='data processing on databricks',
            image=image_repo_name + '/databricks-notebook:latest',
            arguments=[
                '-r', dsl.RUN_ID_PLACEHOLDER,
                '-p', '{"argument_one":"param one","argument_two":"param two"}'
            ]
        ).apply(use_databricks_secret())

        operations['preprocess'] = dsl.ContainerOp(
            name='preprocess',
            image=image_repo_name + '/preprocess:latest',
            command=['python'],
            arguments=[
                '/scripts/data.py',
                '--base_path', persistent_volume_path,
                '--data', training_folder,
                '--target', training_dataset,
                '--img_size', image_size,
                '--zipfile', data_download
            ]
        )

        operations['preprocess'].after(operations['data processing on databricks'])  # noqa: E501

        #  train
        #  TODO: read set of parameters from config file
        with dsl.ParallelFor([{'epochs': 1, 'lr': 0.0001}, {'epochs': 2, 'lr': 0.0002}, {'epochs': 3, 'lr': 0.0003}]) as item:  # noqa: E501
            operations['training'] = dsl.ContainerOp(
                name="training",
                image=image_repo_name + '/training:latest',
                command=['python'],
                arguments=[
                    '/scripts/train.py',
                    '--base_path', persistent_volume_path,
                    '--data', training_folder,
                    '--epochs', item.epochs,
                    '--batch', batch,
                    '--image_size', image_size,
                    '--lr', item.lr,
                    '--outputs', model_folder,
                    '--dataset', training_dataset
                ],
                output_artifact_paths={    # change output_artifact_paths to file_outputs after this PR is merged https://github.com/kubeflow/pipelines/pull/2334 # noqa: E501
                    'mlpipeline-metrics': '/mlpipeline-metrics.json',
                    'mlpipeline-ui-metadata': '/mlpipeline-ui-metadata.json'
                }
                ).add_env_variable(V1EnvVar(name="RUN_ID", value=dsl.RUN_ID_PLACEHOLDER)).add_env_variable(V1EnvVar(name="MLFLOW_TRACKING_URI", value=mlflow_url)).add_env_variable(V1EnvVar(name="GIT_PYTHON_REFRESH", value='quiet'))  # noqa: E501

        operations['training'].after(operations['preprocess'])

        operations['evaluate'] = dsl.ContainerOp(
            name='evaluate',
            image="busybox",
            command=['sh', '-c'],
            arguments=[
                'echo',
                'Life is Good!'
            ]

        )
        operations['evaluate'].after(operations['training'])

        # Register kubeflow artifacts model
        operations['register to kubeflow'] = dsl.ContainerOp(
            name='register to kubeflow',
            image=image_repo_name + '/registerartifacts:latest',
            command=['python'],
            arguments=[
                '/scripts/registerartifacts.py',
                '--base_path', persistent_volume_path,
                '--model', 'latest.h5',
                '--model_name', model_name,
                '--data', training_folder,
                '--dataset', training_dataset,
                '--run_id', dsl.RUN_ID_PLACEHOLDER
            ]
        ).apply(use_azure_secret())
        operations['register to kubeflow'].after(operations['evaluate'])

        # register model
        operations['register to AML'] = dsl.ContainerOp(
            name='register to AML',
            image=image_repo_name + '/register:latest',
            command=['python'],
            arguments=[
                '/scripts/register.py',
                '--base_path', persistent_volume_path,
                '--model', 'latest.h5',
                '--model_name', model_name,
                '--tenant_id', "$(AZ_TENANT_ID)",
                '--service_principal_id', "$(AZ_CLIENT_ID)",
                '--service_principal_password', "$(AZ_CLIENT_SECRET)",
                '--subscription_id', "$(AZ_SUBSCRIPTION_ID)",
                '--resource_group', resource_group,
                '--workspace', workspace,
                '--run_id', dsl.RUN_ID_PLACEHOLDER
            ]
        ).apply(use_azure_secret())
        operations['register to AML'].after(operations['register to kubeflow'])

        # register model to mlflow
        operations['register to mlflow'] = dsl.ContainerOp(
            name='register to mlflow',
            image=image_repo_name + '/register-mlflow:latest',
            command=['python'],
            arguments=[
                '/scripts/register.py',
                '--model', 'model',
                '--model_name', model_name,
                '--experiment_name', 'mexicanfood',
                '--run_id', dsl.RUN_ID_PLACEHOLDER
            ]
        ).apply(use_azure_secret()).add_env_variable(V1EnvVar(name="MLFLOW_TRACKING_URI", value=mlflow_url))  # noqa: E501
        operations['register to mlflow'].after(operations['register to AML'])

        # operations['deploy'] = dsl.ContainerOp(
        #     name='deploy',
        #     image=image_repo_name + '/deploy:latest',
        #     command=['sh'],
        #     arguments=[
        #         '/scripts/deploy.sh',
        #         '-n', model_name,
        #         '-m', model_name,
        #         '-t', "$(AZ_TENANT_ID)",
        #         '-r', resource_group,
        #         '-w', workspace,
        #         '-s', "$(AZ_CLIENT_ID)",
        #         '-p', "$(AZ_CLIENT_SECRET)",
        #         '-u', "$(AZ_SUBSCRIPTION_ID)",
        #         '-b', persistent_volume_path,
        #         '-x', dsl.RUN_ID_PLACEHOLDER
        #     ]
        # ).apply(use_azure_secret())
        # operations['deploy'].after(operations['register'])

        for _, op_1 in operations.items():
            op_1.container.set_image_pull_policy("Always")
            op_1.add_volume(
                k8s_client.V1Volume(
                    name='azure',
                    persistent_volume_claim=k8s_client.V1PersistentVolumeClaimVolumeSource(claim_name='azure-managed-file')  # noqa: E501
                    )
            ).add_volume_mount(k8s_client.V1VolumeMount(
                mount_path='/mnt/azure', name='azure'))


if __name__ == '__main__':
    compiler.Compiler().compile(tacosandburritos_train, 'pipeline.tar.gz')
