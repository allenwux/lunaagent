from sqlalchemy import Column, Integer, String
from Agent import Base, Session

class APIVersion(Base):
    """description of class"""
    
    __tablename__ = 'agent_apiversions'

    Id = Column(Integer, primary_key = True)

    DeploymentName = Column(String)

    ProductName = Column(String)

    VersionName = Column(String)

    RealTimePredictAPI = Column(String)

    TrainModelAPI = Column(String)
    
    BatchInferenceAPI = Column(String)

    DeployModelAPI = Column(String)

    AuthenticationType = Column(String)

    CreatedTime = Column(String)

    LastUpdatedTime = Column(String)

    VersionSourceType = Column(String)

    ProjectFileUrl = Column(String)

    AMLWorkspaceId = Column(Integer)

    AuthenticationKeySecretName = Column(String)

    PublisherId = Column(String)

    ConfigFile = Column(String)

    @staticmethod
    def Get(productName, deploymentName, versionName, publisherId):
        session = Session()
        version = session.query(APIVersion).filter_by(ProductName = productName, DeploymentName = deploymentName, VersionName = versionName, PublisherId = publisherId).first()
        session.close()
        return version

    @staticmethod
    def MergeWithDelete(apiVersions, publisherId):
        session = Session()
        try:
            dbAPIVersions = session.query(APIVersion).all()
            for dbAPIVersion in dbAPIVersions:
                if dbAPIVersion.PublisherId.lower() != publisherId.lower():
                    continue;
                # If the subscription is removed in the control plane, remove it from the agent
                try:
                    next(item for item in apiVersions if 
                         item["DeploymentName"] == dbAPIVersion.DeploymentName
                         and item["ProductName"] == dbAPIVersion.ProductName
                         and item["VersionName"] == dbAPIVersion.VersionName
                         and item["PublisherId"].lower() == dbAPIVersion.PublisherId.lower())
                except StopIteration:
                    session.delete(dbAPIVersion)

            for apiVersion in apiVersions:
                dbAPIVersion = session.query(APIVersion).filter_by(ProductName = apiVersion["ProductName"], 
                                                                   DeploymentName = apiVersion["DeploymentName"], 
                                                                   VersionName = apiVersion["VersionName"], 
                                                                   PublisherId = apiVersion["PublisherId"]).first()
                if dbAPIVersion:
                    dbAPIVersion.LastUpdatedTime = apiVersion["LastUpdatedTime"]
                    dbAPIVersion.ConfigFile = apiVersion["ConfigFile"]
                else:
                    dbAPIVersion = APIVersion(**apiVersion)
                    session.add(dbAPIVersion)

            session.commit()
        except Exception as e:
            session.rollback()
            raise

        finally:
            session.close()
