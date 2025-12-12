pipeline {
    agent any
    
    environment {
        // Docker Configuration
        DOCKER_REGISTRY = 'docker.io'
        CUSTOM_ODOO_IMAGE = "kalla-bju-odoo:${env.BUILD_NUMBER}"
        POSTGRES_IMAGE = 'postgres:15'
        
        // Odoo Configuration
        ODOO_PORT = '8069'
        POSTGRES_PORT = '5432'
        ODOO_CONTAINER_NAME = "odoo-enterprise-${env.BUILD_NUMBER}"
        POSTGRES_CONTAINER_NAME = "odoo-postgres-${env.BUILD_NUMBER}"
        
        // Database Configuration
        POSTGRES_DB = 'odoo'
        POSTGRES_USER = 'odoo'
        POSTGRES_PASSWORD = credentials('odoo-postgres-password')
        
        // Odoo Enterprise Configuration
        ODOO_ADMIN_PASSWORD = credentials('odoo-admin-password')
        ODOO_ENTERPRISE_ADDONS = '/mnt/enterprise-addons'
        
        // Docker Network
        NETWORK_NAME = "odoo-network-${env.BUILD_NUMBER}"
        
        // Deployment Environment
        DEPLOY_ENV = "${params.ENVIRONMENT ?: 'staging'}"
        STAGING_SERVER = '192.168.101.105'
    }
    
    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['staging', 'production'],
            description: 'Select deployment environment'
        )
        string(
            name: 'ODOO_VERSION',
            defaultValue: '18.0',
            description: 'Odoo version to deploy'
        )
        booleanParam(
            name: 'CLEAN_DEPLOYMENT',
            defaultValue: false,
            description: 'Clean deployment (remove existing volumes)'
        )
    }
    
    stages {
        stage('Preparation') {
            steps {
                script {
                    echo "Starting Odoo Enterprise deployment for ${DEPLOY_ENV} environment"
                    echo "Odoo Version: ${params.ODOO_VERSION}"
                    echo "Build Number: ${env.BUILD_NUMBER}"
                }
            }
        }
        
        stage('Build Custom Odoo Image') {
            steps {
                script {
                    echo "Building custom Odoo image with addons..."
                    sh """
                        docker build -t ${CUSTOM_ODOO_IMAGE} .
                    """
                }
            }
        }
        
        stage('Cleanup Old Containers') {
            steps {
                script {
                    echo "Cleaning up old containers and networks..."
                    sh '''
                        # Stop and remove old containers if they exist
                        docker stop ${ODOO_CONTAINER_NAME} || true
                        docker rm ${ODOO_CONTAINER_NAME} || true
                        docker stop ${POSTGRES_CONTAINER_NAME} || true
                        docker rm ${POSTGRES_CONTAINER_NAME} || true
                        
                        # Remove old network if exists
                        docker network rm ${NETWORK_NAME} || true
                        
                        # Clean volumes if requested
                        if [ "${params.CLEAN_DEPLOYMENT}" = "true" ]; then
                            echo "Performing clean deployment - removing volumes..."
                            docker volume rm odoo-data || true
                            docker volume rm odoo-postgres-data || true
                        fi
                        
                        # Clean up old images (keep last 5 builds)
                        docker images kalla-bju-odoo --format "{{.Tag}}" | sort -rn | tail -n +6 | xargs -r -I {} docker rmi kalla-bju-odoo:{} || true
                    '''
                }
            }
        }
        
        stage('Pull PostgreSQL Image') {
            steps {
                script {
                    echo "Pulling PostgreSQL image..."
                    sh """
                        docker pull ${POSTGRES_IMAGE}
                    """
                }
            }
        }
        
        stage('Create Docker Network') {
            steps {
                script {
                    echo "Creating Docker network..."
                    sh """
                        docker network create ${NETWORK_NAME}
                    """
                }
            }
        }
        
        stage('Deploy PostgreSQL') {
            steps {
                script {
                    echo "Deploying PostgreSQL database..."
                    sh """
                        docker run -d \
                            --name ${POSTGRES_CONTAINER_NAME} \
                            --network ${NETWORK_NAME} \
                            -e POSTGRES_DB=${POSTGRES_DB} \
                            -e POSTGRES_USER=${POSTGRES_USER} \
                            -e POSTGRES_PASSWORD=${POSTGRES_PASSWORD} \
                            -v odoo-postgres-data:/var/lib/postgresql/data \
                            ${POSTGRES_IMAGE}
                    """
                    
                    // Wait for PostgreSQL to be ready
                    echo "Waiting for PostgreSQL to be ready..."
                    sh """
                        for i in {1..30}; do
                            if docker exec ${POSTGRES_CONTAINER_NAME} pg_isready -U ${POSTGRES_USER}; then
                                echo "PostgreSQL is ready!"
                                break
                            fi
                            echo "Waiting for PostgreSQL... (\$i/30)"
                            sleep 2
                        done
                    """
                }
            }
        }
        
        stage('Deploy Odoo Enterprise') {
            steps {
                script {
                    echo "Deploying Odoo Enterprise with custom addons..."
                    sh """
                        docker run -d \
                            --name ${ODOO_CONTAINER_NAME} \
                            --network ${NETWORK_NAME} \
                            -p ${ODOO_PORT}:8069 \
                            -e HOST=${POSTGRES_CONTAINER_NAME} \
                            -e USER=${POSTGRES_USER} \
                            -e PASSWORD=${POSTGRES_PASSWORD} \
                            -v odoo-data:/var/lib/odoo \
                            --restart unless-stopped \
                            ${CUSTOM_ODOO_IMAGE}
                    """
                }
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    echo "Performing health check..."
                    sh """
                        # Wait for Odoo to start
                        sleep 15
                        
                        # Check if container is running
                        if ! docker ps | grep -q ${ODOO_CONTAINER_NAME}; then
                            echo "ERROR: Odoo container is not running!"
                            docker logs ${ODOO_CONTAINER_NAME}
                            exit 1
                        fi
                        
                        # Check if Odoo is responding
                        for i in {1..30}; do
                            if curl -f http://localhost:${ODOO_PORT}/web/database/selector 2>/dev/null; then
                                echo "Odoo is responding!"
                                break
                            fi
                            echo "Waiting for Odoo to respond... (\$i/30)"
                            sleep 2
                        done
                    """
                }
            }
        }
        
        stage('Display Deployment Info') {
            steps {
                script {
                    echo """
                    ========================================
                    Odoo Enterprise Deployment Complete!
                    ========================================
                    Environment: ${DEPLOY_ENV}
                    Odoo Version: ${params.ODOO_VERSION}
                    Odoo URL: http://localhost:${ODOO_PORT}
                    Custom Image: ${CUSTOM_ODOO_IMAGE}
                    
                    Container Names:
                    - Odoo: ${ODOO_CONTAINER_NAME}
                    - PostgreSQL: ${POSTGRES_CONTAINER_NAME}
                    
                    Network: ${NETWORK_NAME}
                    
                    Volumes:
                    - odoo-data: Odoo data
                    - odoo-postgres-data: PostgreSQL data
                    
                    Custom Addons Included:
                    - All JST modules
                    - Base tier validation modules
                    - Dashboard modules (ks_dashboard_ninja, ks_dn_advance)
                    - SQL editor and other custom modules
                    ========================================
                    """
                }
            }
        }
    }
    
    post {
        success {
            echo "Odoo Enterprise deployment completed successfully!"
            // You can add notifications here (Slack, Email, etc.)
        }
        
        failure {
            echo "Odoo Enterprise deployment failed!"
            script {
                // Capture logs for debugging
                sh """
                    echo "=== Odoo Logs ==="
                    docker logs ${ODOO_CONTAINER_NAME} || true
                    echo "=== PostgreSQL Logs ==="
                    docker logs ${POSTGRES_CONTAINER_NAME} || true
                """
            }
            // You can add failure notifications here
        }
        
        always {
            // Cleanup temporary files if any
            cleanWs()
        }
    }
}