FROM odoo:18.0

# Switch to root to install additional packages
USER root

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    vim \
    build-essential \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libldap2-dev \
    libsasl2-dev \
    libssl-dev \
    libjpeg-dev \
    libfreetype6-dev \
    liblcms2-dev \
    libwebp-dev \
    libtiff-dev \
    tcl-dev \
    tk-dev \
    && rm -rf /var/lib/apt/lists/*

# Create custom addons directory
RUN mkdir -p /mnt/extra-addons

# Copy all custom addons
COPY Kalla-BJU-Transporter /mnt/extra-addons/Kalla-BJU-Transporter

# Copy requirements files for pip installation
COPY Kalla-BJU-Transporter/ks_dashboard_ninja/requirements.txt /tmp/ks_dashboard_ninja_requirements.txt
COPY Kalla-BJU-Transporter/ks_dn_advance/requirements.txt /tmp/ks_dn_advance_requirements.txt

# Install Python dependencies
RUN pip3 install --break-system-packages --no-cache-dir -r /tmp/ks_dashboard_ninja_requirements.txt && \
    pip3 install --break-system-packages --no-cache-dir -r /tmp/ks_dn_advance_requirements.txt

# Set proper permissions
RUN chown -R odoo:odoo /mnt/extra-addons/Kalla-BJU-Transporter

# Switch back to odoo user
USER odoo

# Set the addons path
ENV ODOO_ADDONS_PATH=/mnt/extra-addons

# Expose Odoo port
EXPOSE 8069 8071 8072

# Set the default command
CMD ["odoo"]
