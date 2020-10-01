from sqlalchemy import Column, Integer, String, DateTime, or_
from Agent import Base, Session, app, key_vault_helper
from Agent.Data.AMLWorkspace import AMLWorkspace
from Agent.Data.AgentUser import AgentUser
from Agent.Exception.LunaExceptions import LunaServerException, LunaUserException
from http import HTTPStatus
import os

class APISubscription(Base):
    """description of class"""

    __tablename__ = 'agent_subscriptions'

    Id = 0

    SubscriptionId = Column(String, primary_key = True)

    DeploymentName = Column(String)

    ProductName = Column(String)

    ProductType = Column(String)

    Owner = Column(String)

    Name = Column(String)

    Status = Column(String)

    HostType = Column(String)

    CreatedTime = Column(DateTime)

    BaseUrl = Column(String)

    PrimaryKeySecretName = Column(String)

    SecondaryKeySecretName = Column(String)

    AMLWorkspaceId = Column(Integer)

    AMLWorkspaceComputeClusterName = Column(String)

    AMLWorkspaceDeploymentTargetType = Column(String)

    AMLWorkspaceDeploymentClusterName = Column(String)

    AgentId = Column(String)

    PublisherId = Column(String)
    
    OfferName = Column(String)

    PlanName = Column(String)

    AMLWorkspaceName = ""

    AvailablePlans = []

    Users = []

    Admins = []

    PrimaryKey = ""

    SecondaryKey = ""

    
    @staticmethod
    def Update(subscription):
        session = Session()
        dbSubscription = session.query(APISubscription).filter_by(SubscriptionId = subscription.SubscriptionId).first()
        workspace = AMLWorkspace.Get(subscription.AMLWorkspaceName)
        if not workspace:
            raise LunaUserException(HTTPStatus.BAD_REQUEST, "The workspace {} doesn't exist or you don't have permission to access it.".format(subscription.AMLWorkspaceName))
        dbSubscription.AMLWorkspaceId = workspace.Id
        dbSubscription.AMLWorkspaceComputeClusterName = subscription.AMLWorkspaceComputeClusterName
        dbSubscription.AMLWorkspaceDeploymentTargetType = subscription.AMLWorkspaceDeploymentTargetType
        dbSubscription.AMLWorkspaceDeploymentClusterName = subscription.AMLWorkspaceDeploymentClusterName
        session.commit()
        session.close()
        # update
        return

    @staticmethod
    def Get(subscriptionId, objectId="Admin"):
        """ the function will should only be called in local mode, otherwise, the keys might be out of date! """
        if objectId != "Admin":
            # validate the userId
            users = AgentUser.ListAllBySubscriptionId(subscriptionId)
            if not any(user.ObjectId == objectId for user in users):
                raise LunaUserException(HTTPStatus.FORBIDDEN, "The subscription {} doesn't exist or you don't have permission to access it.".format(subscriptionId))

        session = Session()
        subscription = session.query(APISubscription).filter_by(SubscriptionId = subscriptionId).first()
        session.close()
        if not subscription:
            return None
        subscription.PrimaryKey = key_vault_helper.get_secret(subscription.PrimaryKeySecretName)
        subscription.SecondaryKey = key_vault_helper.get_secret(subscription.SecondaryKeySecretName)
        if os.environ["AGENT_MODE"] == "LOCAL" and objectId == "Admin":
            subscription.Admins = AgentUser.ListAllAdmin()
            subscription.Users = AgentUser.ListAllBySubscriptionId(subscriptionId)
            subscription.AvailablePlans = ["Basic", "Premium"]
        return subscription

    @staticmethod
    def GetByKey(subscriptionKey):
        session = Session()
        secret_name = key_vault_helper.find_secret_name_by_value(subscriptionKey)
        if secret_name:
            subscription = session.query(APISubscription).filter(or_(APISubscription.PrimaryKeySecretName == secret_name, APISubscription.SecondaryKeySecretName == secret_name)).first()            
        else:
            subscription = None
        session.close()
        return subscription

    @staticmethod
    def ListAllByWorkspaceName(workspaceName):
        session = Session()
        workspace = AMLWorkspace.Get(workspaceName)
        subscriptions = session.query(APISubscription).filter_by(AMLWorkspaceId = workspace.Id).all()
        session.close()
        return subscriptions

    @staticmethod
    def ListAll():
        session = Session()
        subscriptions = session.query(APISubscription).all()
        session.close()
        return subscriptions

    @staticmethod
    def ListAllByUserObjectId(objectId):
        subscriptions = APISubscription.ListAll()
        result = []
        for subscription in subscriptions:
            users = AgentUser.ListAllBySubscriptionId(subscription.SubscriptionId)
            if any(user.ObjectId == objectId for user in users):
                result.append(subscription)
        return result

    @staticmethod
    def MergeWithDelete(subscriptions, publisherId):
        session = Session()
        try:
            dbSubscriptions = session.query(APISubscription).all()
            for dbSubscription in dbSubscriptions:
                if dbSubscription.PublisherId.lower() != publisherId.lower():
                    continue;
                # If the subscription is removed in the control plane, remove it from the agent
                try:
                    next(item for item in subscriptions if item["SubscriptionId"].lower() == dbSubscription.SubscriptionId.lower() and item["PublisherId"].lower() == dbSubscription.PublisherId.lower())
                except StopIteration:
                    session.delete(dbSubscription)

            for subscription in subscriptions:
                dbSubscription = session.query(APISubscription).filter_by(SubscriptionId = subscription["SubscriptionId"]).first()
                if dbSubscription:
                    dbSubscription.DeploymentName = subscription["DeploymentName"]
                    dbSubscription.ProductName = subscription["ProductName"]
                    dbSubscription.ProductType = subscription["ProductType"]
                    dbSubscription.Name = subscription["Name"]
                    dbSubscription.Status = subscription["Status"]
                    dbSubscription.HostType = subscription["HostType"]
                    dbSubscription.BaseUrl = subscription["BaseUrl"]
                    if key_vault_helper.get_secret(dbSubscription.PrimaryKeySecretName) != subscription["PrimaryKey"]:
                        key_vault_helper.set_secret(dbSubscription.PrimaryKeySecretName, subscription["PrimaryKey"])
                    if key_vault_helper.get_secret(dbSubscription.SecondaryKeySecretName) != subscription["SecondaryKey"]:
                        key_vault_helper.set_secret(dbSubscription.SecondaryKeySecretName, subscription["SecondaryKey"])
                else:
                    dbSubscription = APISubscription(**subscription)
                    dbSubscription.PrimaryKeySecretName = 'primarykey-{}'.format(dbSubscription.SubscriptionId)
                    dbSubscription.SecondaryKeySecretName = 'secondarykey-{}'.format(dbSubscription.SubscriptionId)
                    key_vault_helper.set_secret(dbSubscription.PrimaryKeySecretName, dbSubscription.PrimaryKey)
                    key_vault_helper.set_secret(dbSubscription.SecondaryKeySecretName, dbSubscription.SecondaryKey)
                    session.add(dbSubscription)

            session.commit()
        except:
            session.rollback()
            raise

        finally:
            session.close()
