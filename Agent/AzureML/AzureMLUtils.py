from uuid import uuid4
from azureml.core import Workspace, Experiment, Model
from azureml.core.webservice import AksWebservice, Webservice, AciWebservice
from azureml.pipeline.core import PublishedPipeline
from azureml.core.authentication import ServicePrincipalAuthentication
from luna.utils import ProjectUtils
from Agent import key_vault_client
import json
import tempfile
import zipfile
import os
from Agent.Exception.LunaExceptions import LunaServerException, LunaUserException
from http import HTTPStatus

class AzureMLUtils(object):
    """The utlitiy class to execute and monitor runs in AML"""
    _utils=None
    
    def GetOperationNameByVerb(self, verb):
        if verb == 'deploy' or verb == 'batchinference' or verb == 'train':
            return verb
        return self._utils.GetOperationNameByVerb(verb)

    def GetOperationNameByNoun(self, noun):
        if noun == 'models':
            return 'train'
        if noun == 'inferenceresult':
            return 'batchinference'
        if noun == 'endpoints':
            return 'deploy'

        return self._utils.GetOperationNameByNoun(noun)

    def get_workspace_info_from_resource_id(self, resource_id):
        infoList = resource_id.split('/')
        subscriptionId = infoList[2]
        resourceGroupName = infoList[4]
        workspaceName = infoList[-1]
        return subscriptionId, resourceGroupName, workspaceName

    def __init__(self, workspace, config_file=None):
        if workspace.AADApplicationSecret:
            secret = workspace.AADApplicationSecret
        else:
            secret = key_vault_client.get_secret(workspace.AADApplicationSecretName).value
        auth = ServicePrincipalAuthentication(
            tenant_id = workspace.AADTenantId,
            service_principal_id = workspace.AADApplicationId,
            service_principal_password = secret)
        subscriptionId, resourceGroupName, workspaceName = self.get_workspace_info_from_resource_id(workspace.ResourceId)
        ws = Workspace(subscriptionId, resourceGroupName, workspaceName, auth)
        self._workspace = ws
        if config_file:
            self._utils = ProjectUtils(luna_config_file = config_file, run_mode='azureml')

    def get_pipeline_id_from_url(self, url):
        list = url.split('/')
        return list[-1]

    def submitPipelineRun(self, pipelineUrl, productName, deploymentName, apiVersion, entryPoint, userInput, predecessorOperationId, userId, subscriptionId):
        operationId = str('a' + uuid4().hex[1:])
        experimentName = subscriptionId
        exp = Experiment(self._workspace, experimentName)
        tags={'userId': userId, 
              'productName': productName, 
              'deploymentName': deploymentName, 
              'apiVersion': apiVersion,
              'operationName': entryPoint,
              'operationId': operationId,
              'subscriptionId': subscriptionId,
              'predecessorOperationId': predecessorOperationId}
        parameters={'userId': userId, 
              'userInput': userInput,
              'productName': productName, 
              'deploymentName': deploymentName, 
              'apiVersion': apiVersion,
              'operationName': entryPoint,
              'operationId': operationId,
              'subscriptionId': subscriptionId,
              'predecessorOperationId': predecessorOperationId}
        pipeline = PublishedPipeline.get(workspace = self._workspace, id = self.get_pipeline_id_from_url(pipelineUrl))
        exp.submit(pipeline, tags = tags, pipeline_parameters=parameters)
        return operationId

    def runProject(self, productName, deploymentName, apiVersion, operationVerb, userInput, predecessorOperationId, userId, subscriptionId, computeCluster="default", luna_config_file = 'luna_config.yml'):
        operationId = str('a' + uuid4().hex[1:])
        experimentName = subscriptionId
        entryPoint = self.GetOperationNameByVerb(operationVerb)
        if entryPoint:
            run_id = self._utils.RunProject(azureml_workspace = self._workspace, 
                                entry_point = entryPoint, 
                                experiment_name = experimentName, 
                                parameters={'operationId': operationId, 
                                            'userId': userId,
                                            'userInput': userInput,
                                            'productName': productName,
                                            'deploymentName': deploymentName,
                                            'apiVersion': apiVersion,
                                            'subscriptionId': subscriptionId,
                                            'predecessorOperationId': predecessorOperationId}, 
                                tags={'userId': userId, 
                                        'productName': productName, 
                                        'deploymentName': deploymentName, 
                                        'apiVersion': apiVersion,
                                        'operationName': entryPoint,
                                        'subscriptionId': subscriptionId,
                                        'predecessorOperationId': predecessorOperationId,
                                        'operationId': operationId},
                                compute_cluster= computeCluster)
        else:
            raise LunaUserException(HTTPStatus.NOT_FOUND, 'Operation "{}" in not supported in current service.'.format(operationVerb))
        return operationId

    def getOperationStatus(self, operationVerb, operationId, userId, subscriptionId):
        experimentName = subscriptionId
        exp = Experiment(self._workspace, experimentName)
        operationName = self.GetOperationNameByVerb(operationVerb)
        tags = {'userId': userId,
                'operationId': operationId,
                'operationName': operationName,
                'subscriptionId': subscriptionId}
        runs = exp.get_runs(type='azureml.PipelineRun', tags=tags)
        try:
            run = next(runs)
            result = {'operationId': operationId,
                      'status': run.status
                }
            return result
        except StopIteration:
            raise LunaUserException(HTTPStatus.NOT_FOUND, 'Operation "{}" with id {} does not exist.'.format(operationVerb, operationId))

    def listAllOperations(self, operationVerb, userId, subscriptionId):
        experimentName = subscriptionId
        operationName = self.GetOperationNameByVerb(operationVerb)
        exp = Experiment(self._workspace, experimentName)
        tags = {'userId': userId,
                'operationName': operationName,
                'subscriptionId': subscriptionId}
        runs = exp.get_runs(type='azureml.PipelineRun', tags=tags)
        resultList = []
        while True:
            try:
                run = next(runs)
                result = {'operationId': run.tags["operationId"],
                        'status': run.status
                    }
                resultList.append(result)
            except StopIteration:
                break
        return resultList

    def getOperationOutput(self, operationNoun, operationId, userId, subscriptionId, downloadFiles = True):
        operationName = self.GetOperationNameByNoun(operationNoun)

        if operationName == 'train':
            
            tags = [['userId', userId], ['modelId', operationId], ['subscriptionId', subscriptionId]]
            models = Model.list(self._workspace, tags = tags)
            if len(models) == 0:
                return None
            model = models[0]
            result = {'id': operationId,
                      'description': model.description,
                      'created_time': model.created_time}
            return result, "model"

        if operationName == 'deploy':
            
            tags = [['userId', userId], ['endpointId', operationId], ['subscriptionId', subscriptionId]]
            endpoints = Webservice.list(self._workspace, tags = tags)
            if len(endpoints) == 0:
                return None, None
            endpoint = endpoints[0]
            primaryKey, secondaryKey = endpoint.get_keys()
            result = {'id': operationId,
                      'description': endpoint.description,
                      'created_time': endpoint.created_time,
                      'scoring_uri': endpoint.scoring_uri,
                      'primary_key': primaryKey,
                      'secondary_key': secondaryKey}

            return result, "endpoint"
        
        tags = {'userId': userId,
                'operationId': operationId,
                'operationName': operationName,
                'subscriptionId': subscriptionId}

        experimentName = subscriptionId
        exp = Experiment(self._workspace, experimentName)
        runs = exp.get_runs(type='azureml.PipelineRun', tags=tags)
        try:
            run = next(runs)
            child_runs = run.get_children()
            child_run = next(child_runs)
            outputType = self._utils.GetOutputType(operationName)
            if outputType == 'json':
                with tempfile.TemporaryDirectory() as tmp:
                    path = os.path.join(tmp, 'output.json')
                    files = child_run.download_file('/outputs/output.json', path)
                    with open(path) as file:
                        return json.load(file), "json"
            elif outputType == 'file':
                if downloadFiles:
                        tmp = tempfile.TemporaryDirectory().name
                        path = os.path.join(tmp, "outputs")
                        zip_file_path = os.path.join(tmp, "output_{}.zip".format(operationId))
                        files = child_run.download_files("/outputs", path, append_prefix=False)
                        zipf = zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED)
                        self.zipdir(path, zipf, "outputs")
                        zipf.close()
                        return zip_file_path, "file"
                else:
                    return "file", "file"
        except StopIteration:
            return None

    def zipdir(self, path, ziph, dir):
    # ziph is zipfile handle
        for root, dirs, files in os.walk(path):
            for file in files:
                ziph.write(os.path.join(root, file), arcname = os.path.join(dir, file))

    def listAllOperationOutputs(self, operationNoun, userId, subscriptionId):
        operationName = self.GetOperationNameByNoun(operationNoun)
        experimentName = subscriptionId
        exp = Experiment(self._workspace, experimentName)
        tags = {'userId': userId,
                'operationName': operationName,
                'subscriptionId': subscriptionId}
        runs = exp.get_runs(type='azureml.PipelineRun', tags=tags)
        results = []
        while True:
            try:
                run = next(runs)
                output, outputType = self.getOperationOutput(operationNoun, run.tags["operationId"], userId, subscriptionId, downloadFiles=False)
                if output:
                    if outputType == "model" or outputType == "endpoint":
                        results.append(output)
                    elif outputType == "json":
                        results.append({"operationId": run.tags["operationId"], "output": result})
                    elif outputType == "file":
                        results.append({"operationId": run.tags["operationId"], "outputType": "file"})
            except StopIteration:
                break
        return results

    def deleteOperationOutput(self, productName, deploymentName, apiVersion, operationName, operationId, userId, subscriptionId):
        return

    def getComputeClusters(self):
        clusters = self._workspace.compute_targets
        computeClusters = []
        for cluster in clusters.values():
            if cluster.type == "AmlCompute":
                computeClusters.append(cluster.name)
        return computeClusters

    def getDeploymentClusters(self):
        clusters = self._workspace.compute_targets
        deploymentClusters = []
        for cluster in clusters.values():
            if cluster.type == "AKS":
                deploymentClusters.append(cluster.name)
        return deploymentClusters