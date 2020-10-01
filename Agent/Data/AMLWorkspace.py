from sqlalchemy import Column, Integer, String
from Agent import Base, Session, key_vault_helper
from Agent.AzureML.AzureMLUtils import AzureMLUtils
import uuid

class AMLWorkspace(Base):
    """description of class"""
    
    __tablename__ = 'agent_amlworkspaces'

    Id = Column(Integer, primary_key = True)

    WorkspaceName = Column(String)

    ResourceId = Column(String)

    AADApplicationId = Column(String)

    AADTenantId = Column(String)

    AADApplicationSecretName = Column(String)

    AADApplicationSecret = ""

    Region = Column(String)

    ComputeClusters = []

    DeploymentClusters = []

    DeploymentTargetTypes = []

    @staticmethod
    def Create(workspace):
        session = Session()
        workspace.AADApplicationSecretName = 'aml-{}'.format(uuid.uuid4())
        key_vault_helper.set_secret(workspace.AADApplicationSecretName, workspace.AADApplicationSecret)
        session.add(workspace)
        session.commit()
        return

    def Update(workspace):
        session = Session()
        dbWorkspace = session.query(AMLWorkspace).filter_by(WorkspaceName = workspace.WorkspaceName).first()
        dbWorkspace.AADApplicationId = workspace.AADApplicationId
        if workspace.AADApplicationSecret != "" and workspace.AADApplicationSecret != "notchanged":
            key_vault_helper.set_secret(dbWorkspace.AADApplicationSecretName, workspace.AADApplicationSecret)
        dbWorkspace.AADTenantId = workspace.AADTenantId
        session.commit()
        # update
        return

    @staticmethod
    def Get(workspaceName):
        session = Session()
        workspace = session.query(AMLWorkspace).filter_by(WorkspaceName = workspaceName).first()
        workspace.AADApplicationSecret = key_vault_helper.get_secret(workspace.AADApplicationSecretName)
        util = AzureMLUtils(workspace)
        workspace.ComputeClusters = util.getComputeClusters()
        workspace.DeploymentClusters = util.getDeploymentClusters()
        workspace.DeploymentTargetTypes = [{
                'id': 'aks',
                'displayName': 'Azure Kubernates Service'
            },
            {
                'id': 'aci',
                'displayName': 'Azure Container Instances'
            }]
        ## never return the workspace secret
        workspace.AADApplicationSecret = "notchanged"
        session.close()
        return workspace

    def GetByIdWithSecrets(workspaceId):
        session = Session()
        workspace = session.query(AMLWorkspace).filter_by(Id = workspaceId).first()
        workspace.AADApplicationSecret = key_vault_helper.get_secret(workspace.AADApplicationSecretName)
        session.close()
        return workspace

    @staticmethod
    def Exist(workspaceName):
        session = Session()
        return len(session.query(AMLWorkspace).filter_by(WorkspaceName = workspaceName).all()) > 0

    @staticmethod
    def ListAll():
        session = Session()
        workspaces = session.query(AMLWorkspace).all()
        for workspace in workspaces:
            workspace.AADApplicationSecret = ""
        return workspaces

    @staticmethod
    def Delete(workspaceName):
        session = Session()
        workspace = session.query(AMLWorkspace).filter_by(WorkspaceName = workspaceName).first()
        session.delete(workspace)
        session.commit()
        return
