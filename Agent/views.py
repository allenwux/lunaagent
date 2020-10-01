"""
Routes and views for the flask application.
"""

from datetime import datetime
from flask import render_template, send_file,redirect
from flask import jsonify, request
from Agent.Code.CodeUtils import CodeUtils
from Agent.AzureML.AzureMLUtils import AzureMLUtils
from Agent.Mgmt.ControlPlane import ControlPlane
from datetime import datetime
from uuid import uuid4
import pathlib
from Agent.Data.APISubscription import APISubscription
from Agent.Data.APIVersion import APIVersion
from sqlalchemy.orm import sessionmaker
from Agent import engine, Session, app, key_vault_client
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
from Agent.Data.AMLWorkspace import AMLWorkspace
from Agent.Data.AgentUser import AgentUser
from Agent.Data.Publisher import Publisher
from Agent.Data.Offer import Offer
from Agent.Exception.LunaExceptions import LunaServerException, LunaUserException
from Agent.Auth.AuthHelper import AuthenticationHelper
import json, os, io
from http import HTTPStatus
import requests


def getToken():
    bearerToken = request.headers.get("Authorization")
    if not bearerToken or not bearerToken.startswith("Bearer "):
        raise LunaUserException(HTTPStatus.FORBIDDEN, "AAD token is required.")
    return bearerToken.replace("Bearer ", "")

def handleExceptions(e):
    if isinstance(e, LunaUserException):
        return e.message, e.http_status_code
    else:
        return 'The server encountered an internal error and was unable to complete your request.', 500

def getMetadata(subscriptionId, isRealTimePredict = False):
    
    apiVersion = request.args.get('api-version')
    if not apiVersion:
        raise LunaUserException(HTTPStatus.BAD_REQUEST, 'The api-version query parameter is not provided.')

    # Verify key first if api-key is provided. Otherwise, try AAD auth
    subscriptionKey = request.headers.get('api-key')
    if subscriptionKey:
        sub = APISubscription.GetByKey(subscriptionKey)
        if not sub:
            raise LunaUserException(HTTPStatus.UNAUTHORIZED, 'The api key is invalid.')
        if subscriptionId != "default" and subscriptionId.lower() != sub.SubscriptionId.lower():
            raise LunaUserException(HTTPStatus.UNAUTHORIZED, "The subscription {} doesn't exist or api key is invalid.".format(subscriptionId))
    else:
        objectId = AuthenticationHelper.ValidateSignitureAndUser(getToken(), subscriptionId)
        sub = APISubscription.Get(subscriptionId, objectId)
        if not sub:
            raise LunaUserException(HTTPStatus.NOT_FOUND, 'The subscription {} does not exist.'.format(subscriptionId))
    
    version = APIVersion.Get(sub.ProductName, sub.DeploymentName, apiVersion, sub.PublisherId)
    if not version:
        raise LunaUserException(HTTPStatus.NOT_FOUND, 'The api version {} does not exist.'.format(apiVersion))

    if isRealTimePredict:
        if os.environ["AGENT_MODE"] == "LOCAL":
            raise LunaUserException(HTTPStatus.BAD_REQUEST, 'Cannot call SaaS service from local agent.')
        if version.AMLWorkspaceId and version.AMLWorkspaceId != 0:
            workspace = AMLWorkspace.GetByIdWithSecrets(version.AMLWorkspaceId)
        else:
            workspace = None
    else:
        if os.environ["AGENT_MODE"] == "SAAS":
            workspace = AMLWorkspace.GetByIdWithSecrets(version.AMLWorkspaceId)
        elif os.environ["AGENT_MODE"] == "LOCAL":
            if (not sub.AMLWorkspaceId) or sub.AMLWorkspaceId == 0:
                raise LunaUserException(HTTPStatus.METHOD_NOT_ALLOWED, 'There is not an Azure Machine Learning workspace configured for this subscription. Please contact your admin to finish the configuration.'.format(version.AMLWorkspaceId))
            workspace = AMLWorkspace.GetByIdWithSecrets(sub.AMLWorkspaceId)
        
        if not workspace:
            raise LunaServerException('The workspace with id {} is not found.'.format(version.AMLWorkspaceId))

        publisher = Publisher.Get(sub.PublisherId)
        if version.VersionSourceType == 'git':
            CodeUtils.getLocalCodeFolder(sub.SubscriptionId, sub.ProductName, sub.DeploymentName, version, pathlib.Path(__file__).parent.absolute(), publisher.ControlPlaneUrl)
    return sub, version, workspace, apiVersion

def getSubscriptionAPIVersionAndWorkspace(subscriptionId, apiVersion):
    sub = APISubscription.Get(subscriptionId)
    version = APIVersion.Get(sub.ProductName, sub.DeploymentName, apiVersion, sub.PublisherId)
    if os.environ["AGENT_MODE"] == "SAAS":
        workspace = AMLWorkspace.GetByIdWithSecrets(version.AMLWorkspaceId)
    elif os.environ["AGENT_MODE"] == "LOCAL":
        workspace = AMLWorkspace.GetByIdWithSecrets(sub.AMLWorkspaceId)

    return sub, version, workspace

@app.route('/predict', methods=['POST'])
@app.route('/<subscriptionId>/predict', methods=['POST'])
def realtimePredict(subscriptionId = 'default'):
    
    sub, version, workspace, apiVersion = getMetadata(subscriptionId, True)
    
    requestUrl = version.RealTimePredictAPI
    headers = {'Content-Type': 'application/json'}
    if version.AuthenticationType == 'Key':
        secret = key_vault_client.get_secret(version.AuthenticationKeySecretName).value
        headers['Authorization'] = 'Bearer {}'.format(secret)
    response = requests.post(requestUrl, json.dumps(request.json), headers=headers)
    if response.ok:
        return response.json(), response.status_code
    return response.text, response.status_code

@app.route('/saas-api/<operationVerb>', methods=['POST'])
@app.route('/api/<subscriptionId>/<operationVerb>', methods=['POST'])
def executeOperation(operationVerb, subscriptionId = 'default'):
    
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)

        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        if version.VersionSourceType == 'git':
            if os.environ["AGENT_MODE"] == "SAAS":
                computeCluster = "default"
            else:
                computeCluster = sub.AMLWorkspaceComputeClusterName
            opId = amlUtil.runProject(sub.ProductName, sub.DeploymentName, apiVersion, operationVerb, json.dumps(request.json), 'na', sub.Owner, sub.SubscriptionId, computeCluster=computeCluster)
        elif version.VersionSourceType == 'amlPipeline':
            url = None
            if operationVerb == 'train':
                url = version.TrainModelAPI

            if url and url != "":
                opId = amlUtil.submitPipelineRun(url, sub.ProductName, sub.DeploymentName, apiVersion, operationVerb, json.dumps(request.json), 'na', sub.Owner, sub.SubscriptionId)
            else:
                return 'The operation {} is not supported'.format(operationVerb)
    
        return jsonify({'operationId': opId})
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/operations/<operationVerb>/<operationId>', methods=['GET'])
@app.route('/api/<subscriptionId>/operations/<operationVerb>/<operationId>', methods=['GET'])
def getOperationStatus(operationVerb, operationId, subscriptionId = 'default'):
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)
        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        result = amlUtil.getOperationStatus(operationVerb, operationId, sub.Owner, sub.SubscriptionId)
        if result:
            return jsonify(result)
        else:
            raise LunaUserException(HTTPStatus.NOT_FOUND, 'Object with id {} does not exist.'.format(operationId))
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/operations/<operationVerb>', methods=['GET'])
@app.route('/api/<subscriptionId>/operations/<operationVerb>', methods=['GET'])
def listOperations(operationVerb, subscriptionId='default'):
    
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)
        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        result = amlUtil.listAllOperations(operationVerb, sub.Owner, sub.SubscriptionId)
        return jsonify(result)
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/<operationNoun>', methods=['GET'])
@app.route('/api/<subscriptionId>/<operationNoun>', methods=['GET'])
def listOperationOutputs(operationNoun, subscriptionId = 'default'):
    
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)
        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        result = amlUtil.listAllOperationOutputs(operationNoun, sub.Owner, sub.SubscriptionId)
        return jsonify(result)
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/<operationNoun>/<operationId>', methods=['GET'])
@app.route('/api/<subscriptionId>/<operationNoun>/<operationId>', methods=['GET'])
def getOperationOutput(operationNoun, operationId, subscriptionId = 'default'):
    
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)
        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        result, outputType = amlUtil.getOperationOutput(operationNoun, operationId, sub.Owner, sub.SubscriptionId)
        if not result:
            raise LunaUserException(HTTP_Status.NOT_FOUND, "The specified operation didn't generate any output.")
        if outputType == "file":
            with open(result, 'rb') as bites:
                return send_file(
                     io.BytesIO(bites.read()),
                     attachment_filename='outputs_{}.zip'.format(operationId),
                     mimetype='application/zip'
                )
        return jsonify(result)
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/<parentOperationNoun>/<parentOperationId>/<operationVerb>', methods=['POST'])
@app.route('/api/<subscriptionId>/<parentOperationNoun>/<parentOperationId>/<operationVerb>', methods=['POST'])
def executeChildOperation(parentOperationNoun, parentOperationId, operationVerb, subscriptionId = 'default'):
    
    try:
        sub, version, workspace, apiVersion = getMetadata(subscriptionId)
        amlUtil = AzureMLUtils(workspace, version.ConfigFile)
        if version.VersionSourceType == 'git':
            if os.environ["AGENT_MODE"] == "SAAS":
                computeCluster = "default"
            else:
                computeCluster = sub.AMLWorkspaceComputeClusterName
            opId = amlUtil.runProject(sub.ProductName, sub.DeploymentName, apiVersion, operationVerb, json.dumps(request.json), parentOperationId, sub.Owner, sub.SubscriptionId, computeCluster=computeCluster)
        elif version.VersionSourceType == 'amlPipeline':
            if parentOperationNoun != 'models':
                return 'The parent resource type {} is not supported'.format(parentOperationNoun)
            url = None
            if operationVerb == 'batchinference':
                url = version.BatchInferenceAPI
            elif operationVerb == 'deploy':
                url = version.DeployModelAPI

            if url and url != "":
                opId = amlUtil.submitPipelineRun(url, sub.ProductName, sub.DeploymentName, apiVersion, operationVerb, json.dumps(request.json), parentOperationId, sub.Owner, sub.SubscriptionId)
            else:
                return 'The operation {} is not supported'.format(operationVerb)
    
        return jsonify({'operationId': opId})
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/saas-api/<operationNoun>/<operationId>', methods=['DELETE'])
@app.route('/api/<subscriptionId>/<operationNoun>/<operationId>', methods=['DELETE'])
def deleteOperationOutput(operationNoun, operationId, subscriptionId = 'default'):
    return jsonify({})


@app.route('/api/management/refreshMetadata', methods=['POST'])
def refreshMetadata():
    try:
        app.logger.info(getToken())
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        controlPlane = ControlPlane(os.environ['AGENT_ID'], os.environ['AGENT_KEY'])
        controlPlane.UpdateMetadataDatabase()
        return "The metadata database is refreshed", 200

    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions', methods=['GET'])
def listAllSubscriptions():
    try:
        objectId = AuthenticationHelper.ValidateSignitureAndUser(getToken())
        if objectId == "Admin":
            subscriptions = APISubscription.ListAll()
        else:
            subscriptions = APISubscription.ListAllByUserObjectId(objectId)
        return jsonify(subscriptions), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions/<subscriptionId>', methods=['GET'])
def getSubscription(subscriptionId):
    try:
        objectId = AuthenticationHelper.ValidateSignitureAndUser(getToken(), subscriptionId)
        subscription = APISubscription.Get(subscriptionId, objectId)
        return jsonify(subscription), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions/<subscriptionId>', methods=['PUT'])
def createOrUpdateSubscription(subscriptionId):
    """ TODO: do we need this API? """
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        subscription = APISubscription(**request.json)
        APISubscription.Update(subscription)
        return jsonify(request.json), 202
    
    except Exception as e:
        return handleExceptions(e)
@app.route('/api/management/subscriptions/<subscriptionId>/users', methods=['GET'])
def listAllSubscriptionUsers(subscriptionId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        users = AgentUser.ListAllBySubscriptionId(subscriptionId)
        return jsonify(users), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions/<subscriptionId>/users/<userId>', methods=['GET'])
def getSubscriptionUser(subscriptionId, userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        user = AgentUser.GetUser(subscriptionId, userId)
        return jsonify(user), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions/<subscriptionId>/users/<userId>', methods=['PUT'])
def addSubscriptionUser(subscriptionId, userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        if AgentUser.GetUser(subscriptionId, userId):
            return "The user with user id {userId} already exists in subscription {subscriptionId}".format(userId = userId, subscriptionId = subscriptionId), 409

        if "ObjectId" not in request.json:
            raise LunaUserException(HTTPStatus.BAD_REQUEST, "The object id is required")
        
        user = AgentUser(**request.json)
        if subscriptionId != user.SubscriptionId:
            return "The subscription id in request body doesn't match the subscription id in request url.", 400
        if userId != user.AADUserId:
            return "The user id in request body doesn't match the user id in request url.", 400
        AgentUser.Create(user)
        return jsonify(request.json), 202
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/subscriptions/<subscriptionId>/users/<userId>', methods=['DELETE'])
def removeSubscriptionUser(subscriptionId, userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        if not AgentUser.GetUser(subscriptionId, userId):
            return "The user with user id {userId} doesn't exist in subscription {subscriptionId}".format(userId = userId, subscriptionId = subscriptionId), 404
        AgentUser.DeleteUser(subscriptionId, userId)
        return jsonify({}), 204
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/admins', methods=['GET'])
def listAllAdmins():
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        admins = AgentUser.ListAllAdmin()
        return jsonify(admins), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/admins/<userId>', methods=['GET'])
def getAdmin(userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        admin = AgentUser.GetAdmin(userId)
        if not admin:
            return "The admin with user id {userId} doesn't exist.".format(userId = userId), 404
        return jsonify(admin), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/admins/<userId>', methods=['PUT'])
def addAdmin(userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        if AgentUser.GetAdmin(userId):
            return "The admin with user id {userId} already exists.".format(userId = userId), 409

        if "ObjectId" not in request.json:
            raise LunaUserException(HTTPStatus.BAD_REQUEST, "The object id is required")
        user = AgentUser(**request.json)

        if user.Role != "Admin":
            return "The role of the admin user must be Admin.", 400
        if userId != user.AADUserId:
            return "The user id in request body doesn't match the user id in request url.", 400
        AgentUser.Create(user)
        return jsonify(request.json), 202
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/admins/<userId>', methods=['DELETE'])
def removeAdmin(userId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        objectId = AuthenticationHelper.GetUserObjectId(getToken())
        admin = AgentUser.GetAdmin(userId)
        if not admin:
            return "The admin with user id {userId} doesn't exist.".format(userId = userId), 404
        if admin.ObjectId.lower() == objectId:
            raise LunaUserException(HTTPStatus.CONFLICT, "Admin cannot remove themselves from Admin list.")
        AgentUser.DeleteAdmin(userId)
        return jsonify({}), 204
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/publishers', methods=['GET'])
def listAllPublishers():
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        publishers = Publisher.ListAll()
        return jsonify(publishers), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/publishers/<publisherId>', methods=['GET'])
def getPublisher(publisherId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        publisher = Publisher.Get(publisherId)
        if not publisher:
            return "The publisher with id {publisherId} doesn't exist.".format(publisherId = publisherId), 404
        return jsonify(publisher), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/publishers/<publisherId>', methods=['PUT'])
def addPublisher(publisherId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        publisher = Publisher(**request.json)

        if publisherId != publisher.PublisherId:
            return "The id in request body doesn't match the publisher id in request url.", 400
        

        if Publisher.Get(publisherId):
            Publisher.Update(publisherId, publisher)
        else:
            Publisher.Create(publisher)
        return jsonify(request.json), 202

    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/publishers/<publisherId>', methods=['DELETE'])
def removePublisher(publisherId):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        if not Publisher.Get(publisherId):
            return "The publisher with id {publisherId} doesn't exist.".format(publisherId = publisherId), 404
        Publisher.Delete(publisherId)
        return jsonify({}), 204
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/amlworkspaces', methods=['GET'])
def listAllAMLWorkspaces():
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        workspaces = AMLWorkspace.ListAll()
        return jsonify(workspaces), 200
    
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/amlworkspaces/<workspaceName>', methods=['GET'])
def getAMLWorkspace(workspaceName):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        workspace = AMLWorkspace.Get(workspaceName)
        if workspace:
            return jsonify(workspace), 200
        else:
            return "Can not find the workspace with name {}".format(workspaceName), 404
        
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/amlworkspaces/<workspaceName>', methods=['PUT'])
def createOrUpdateAMLWorkspace(workspaceName):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        workspace = AMLWorkspace(**request.json)
        if workspaceName != workspace.WorkspaceName:
            return "The workspace name in request body doesn't match the workspace name in request url.", 400
        if AMLWorkspace.Exist(workspaceName):
            AMLWorkspace.Update(workspace)
            return jsonify(request.json), 200
        else:
            AMLWorkspace.Create(workspace)
            return jsonify(request.json), 202
            
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/amlworkspaces/<workspaceName>', methods=['DELETE'])
def deleteAMLWorkspace(workspaceName):
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        if not AMLWorkspace.Exist(workspaceName):
            return "Workspace with name {} doesn't exist.".format(workspaceName), 404

        if len(APISubscription.ListAllByWorkspaceName(workspaceName)) != 0:
            return "The workspace {} is still being used by API subscription. Reconfigure the subscriptions before deleting the workspace.".format(workspaceName), 409
        AMLWorkspace.Delete(workspaceName)
        return jsonify({}), 204
        
    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/agentinfo', methods=['GET'])
def getAgentInfo():
    try:
        AuthenticationHelper.ValidateSignitureAndAdmin(getToken())
        info = {
            "AgentId" : os.environ['AGENT_ID'], 
            "AgentKey" : os.environ['AGENT_KEY'], 
            "AgentAPIEndpoint": os.environ['AGENT_API_ENDPOINT'],
            "AgentAPIConnectionString": "{}:{}@{}".format(os.environ['AGENT_ID'], os.environ['AGENT_KEY'], os.environ['AGENT_API_ENDPOINT'])}
        return jsonify(info), 200

    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/marketplaceOffers', methods=['GET'])
def getMarketplaceOffers():
    try:
        userId = request.args.get('userId')
        if not userId:
            raise LunaUserException(HTTPStatus.BAD_REQUEST, "Query parameter userId is required.")

        offers = Offer.ListMarketplaceOffers(userId)
        return jsonify(offers), 200

    except Exception as e:
        return handleExceptions(e)

@app.route('/api/management/internalOffers', methods=['GET'])
def getInternalOffers():
    try:
        userId = request.args.get('userId')
        if not userId:
            raise LunaUserException(HTTPStatus.BAD_REQUEST, "Query parameter userId is required.")

        offers = Offer.ListInternalOffers(userId)
        return jsonify(offers), 200

    except Exception as e:
        return handleExceptions(e)

@app.route('/')
@app.route('/home')
def home():
    """Renders the home page."""
    return jsonify("This is an API Service.")


@app.route('/')
@app.route('/portal')
def portal():
    return redirect("https://luna-sa.azurewebsites.net/", code=302)