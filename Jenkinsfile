pipeline {
    agent any
    
    environment {
        // Docker Configuration
        CUSTOM_ODOO_IMAGE = 'custom-odoo:18.0'
        
        // Container Names
        ODOO_CONTAINER_NAME = 'env3-odoo'
        
        // Port Configuration
        ODOO_PORT = '8020'
        
        // Database Configuration
        DB_HOST = '192.168.101.105'
        DB_USER = 'postgres'
        DB_PASSWORD = 'postgres'
        DB_PORT = '5432'
        POSTGRES_DB = 'fms_lms_2'
        
        // Odoo Session Configuration
        ODOO_SESSION_COOKIE_NAME = 'odoo_env3_session_id'
        
        // Docker Network
        NETWORK_NAME = 'odoo-network-env3'
        
        // Volume Names
        ODOO_DATA_VOLUME = 'odoo-web-data-2'
    }
    
    parameters {
        booleanParam(
            name: 'CLEAN_DEPLOYMENT',
            defaultValue: false,
            description: 'Clean deployment (remove existing volumes)'
        )
        booleanParam(
            name: 'REBUILD_IMAGE',
            defaultValue: true,
            description: 'Rebuild Odoo Docker image'
        )
    }
    
    stages {
        stage('Preparation') {
            steps {
                script {
                    echo "Starting Odoo Environment 3 deployment"
                    echo "Build Number: ${env.BUILD_NUMBER}"
                    echo "Database: ${POSTGRES_DB}"
                }
            }
        }
        
        stage('Build Custom Odoo Image') {
            when {
                expression { params.REBUILD_IMAGE == true }
            }
            steps {
                script {
                    echo "Building custom Odoo 17.0 image with addons..."
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
                    sh """
                        # Stop and remove old containers if they exist
                        docker stop ${ODOO_CONTAINER_NAME} || true
                        docker rm ${ODOO_CONTAINER_NAME} || true
                        
                        # Remove old network if exists
                        docker network rm ${NETWORK_NAME} || true
                        
                        # Clean volumes if requested
                        if [ "${params.CLEAN_DEPLOYMENT}" = "true" ]; then
                            echo "Performing clean deployment - removing volumes..."
                            docker volume rm ${ODOO_DATA_VOLUME} || true
                            rm -rf ./filestore/* || true
                        fi
                    """
                }
            }
        }
        
        stage('Create Docker Network') {
            steps {
                script {
                    echo "Creating Docker network..."
                    sh """
                        docker network create ${NETWORK_NAME} || true
                    """
                }
            }
        }
        
        stage('Create Required Directories') {
            steps {
                script {
                    echo "Creating required directories..."
                    sh """
                        mkdir -p ./etc
                        mkdir -p ./filestore
                        mkdir -p ./backups
                        mkdir -p ./enterprise
                    """
                }
            }
        }
        
        stage('Deploy Odoo') {
            steps {
                script {
                    echo "Deploying Odoo with custom addons..."
                    sh """
                        docker run -d \
                            --name ${ODOO_CONTAINER_NAME} \
                            --network ${NETWORK_NAME} \
                            -p ${ODOO_PORT}:8069 \
                            -e DB_HOST=${DB_HOST} \
                            -e DB_USER=${DB_USER} \
                            -e DB_PASSWORD=${DB_PASSWORD} \
                            -e DB_PORT=${DB_PORT} \
                            -e ODOO_SESSION_COOKIE_NAME=${ODOO_SESSION_COOKIE_NAME} \
                            -v \$(pwd)/../Kalla-BJU:/mnt/extra-addons/Kalla-BJU \
                            -v \$(pwd)/../Kalla-BJU-Transporter:/mnt/extra-addons/Kalla-BJU-Transporter \
                            -v \$(pwd)/../kict-security:/mnt/extra-addons/kict-security \
                            -v \$(pwd)/../odoo-17.0+e.20241125/odoo/addons:/mnt/extra-addons/enterprise \
                            -v \$(pwd)/enterprise:/mnt/extra-addons \
                            -v \$(pwd)/etc:/etc/odoo \
                            -v \$(pwd)/filestore:/var/lib/odoo/.local/share/Odoo/filestore/${POSTGRES_DB} \
                            -v ${ODOO_DATA_VOLUME}:/var/lib/odoo \
                            -v \$(pwd)/backups:/odoo/backups \
                            --restart always \
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
                        sleep 20
                        
                        # Check if containers are running
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
                    Odoo Environment 3 Deployment Complete!
                    ========================================
                    Odoo Version: 17.0
                    Odoo URL: http://localhost:${ODOO_PORT}
                    
                    Container Names:
                    - Odoo: ${ODOO_CONTAINER_NAME}
                    
                    Network: ${NETWORK_NAME}
                    
                    Volumes Mounted:
                    - ../Kalla-BJU -> /mnt/extra-addons/Kalla-BJU
                    - ../Kalla-BJU-Transporter -> /mnt/extra-addons/Kalla-BJU-Transporter
                    - ../kict-security -> /mnt/extra-addons/kict-security
                    - Enterprise addons mounted
                    - Config: ./etc -> /etc/odoo
                    - Filestore: ./filestore
                    - Backups: ./backups
                    
                    Named Volumes:
                    - ${ODOO_DATA_VOLUME}
                    ========================================
                    """
                }
            }
        }
    }
    
    post {
        success {
            echo "Odoo Environment 3 deployment completed successfully!"
            echo "Access your Odoo instance at http://localhost:${ODOO_PORT}"
        }
        
        failure {
            echo "Odoo Environment 3 deployment failed!"
            script {
                // Capture logs for debugging
                sh """
                    echo "=== Odoo Logs ==="
                    docker logs ${ODOO_CONTAINER_NAME} || true
                """
            }
        }
        
        always {
            echo "Deployment process completed."
        }
    }
}