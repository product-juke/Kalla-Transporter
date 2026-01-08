pipeline {
    agent any
    
    environment {
        // Docker Configuration
        CUSTOM_ODOO_IMAGE = 'custom-odoo:18.0'
    }
    
    parameters {
        choice(
            name: 'ENVIRONMENT',
            choices: ['Staging', 'Production'],
            description: 'Select deployment environment'
        )
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
        stage('Set Environment Variables') {
            steps {
                script {
                    // Common Database Configuration (shared database server)
                    env.DB_HOST = '192.168.101.105'
                    env.DB_USER = 'postgres'
                    env.DB_PASSWORD = 'postgres'
                    env.DB_PORT = '5432'
                    
                    if (params.ENVIRONMENT == 'Staging') {
                        // Staging Environment Configuration
                        env.ODOO_CONTAINER_NAME = 'staging-odoo'
                        env.ODOO_PORT = '8020'
                        env.POSTGRES_DB = 'fms_lms_staging'
                        env.ODOO_SESSION_COOKIE_NAME = 'odoo_staging_session_id'
                        env.NETWORK_NAME = 'odoo-network-staging'
                        env.ODOO_DATA_VOLUME = 'odoo-web-data-staging'
                    } else if (params.ENVIRONMENT == 'Production') {
                        // Production Environment Configuration
                        env.ODOO_CONTAINER_NAME = 'production-odoo'
                        env.ODOO_PORT = '8069'
                        env.POSTGRES_DB = 'fms_lms_production'
                        env.ODOO_SESSION_COOKIE_NAME = 'odoo_production_session_id'
                        env.NETWORK_NAME = 'odoo-network-production'
                        env.ODOO_DATA_VOLUME = 'odoo-web-data-production'
                    }
                    
                    echo "=========================================="
                    echo "Environment: ${params.ENVIRONMENT}"
                    echo "Database Host: ${env.DB_HOST}"
                    echo "Container Name: ${env.ODOO_CONTAINER_NAME}"
                    echo "Odoo Port: ${env.ODOO_PORT}"
                    echo "Database Name: ${env.POSTGRES_DB}"
                    echo "Session Cookie Name: ${env.ODOO_SESSION_COOKIE_NAME}"
                    echo "Network Name: ${env.NETWORK_NAME}"
                    echo "Volume Name: ${env.ODOO_DATA_VOLUME}"
                    echo "=========================================="
                }
            }
        }
        
        stage('Preparation') {
            steps {
                script {
                    echo "Starting Odoo ${params.ENVIRONMENT} deployment"
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
                    Odoo ${params.ENVIRONMENT} Deployment Complete!
                    ========================================
                    Environment: ${params.ENVIRONMENT}
                    Odoo Version: 18.0
                    Odoo URL: http://localhost:${ODOO_PORT}
                    Database Host: ${DB_HOST}
                    
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
            echo "Odoo ${params.ENVIRONMENT} deployment completed successfully!"
            echo "Access your Odoo instance at http://localhost:${ODOO_PORT}"
        }
        
        failure {
            echo "Odoo ${params.ENVIRONMENT} deployment failed!"
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