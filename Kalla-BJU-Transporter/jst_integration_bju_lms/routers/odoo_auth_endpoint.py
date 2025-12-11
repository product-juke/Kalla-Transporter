
from typing import Annotated, Union
from pydantic import BaseModel
from datetime import datetime, timedelta
from jose import JWTError, jwt
from odoo.api import Environment
from odoo.addons.fastapi.dependencies import odoo_env
from odoo.http import request
import json
from xmlrpc.client import ServerProxy

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

SECRET_KEY = "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
router = APIRouter(tags=["Odoo"])


class Token(BaseModel):
    access_token: str
    token_type: str

class User(BaseModel):
    id: int
    username: str
    email: Union[str, None] = None
    full_name: Union[str, None] = None

class ListModelAccess(BaseModel):
    name: str
    model: str
    model_name: str
    group_name: str
    perm_read: bool
    perm_write: bool
    perm_create: bool
    perm_unlink: bool

class ListUser(BaseModel):
    id: int
    email: str
    full_name: str
    access_list: list[ListModelAccess]

class ListProfile(BaseModel):
    id: int
    username: str
    email: str
    full_name: str

class ListModule(BaseModel):
    name: str
    shortdesc: str
    description: str
    author: str
    summary: str
    state: str
    latest_version: str

class ListEmployee(BaseModel):
    id: int
    name: str
    job_title: str
    work_phone: str
    mobile_phone: str
    work_email: str
    active: bool

class PostEmployee(BaseModel):
    name: str
    job_title: Union[str, None] = None
    work_phone: Union[str, None] = None
    mobile_phone: Union[str, None] = None
    work_email: Union[str, None] = None

class PutEmployee(BaseModel):
    id: int
    name: str
    job_title: Union[str, None] = None
    work_phone: Union[str, None] = None
    mobile_phone: Union[str, None] = None
    work_email: Union[str, None] = None

class DeleteEmployee(BaseModel):
    id: int

def create_access_token(data: dict, expires_delta: timedelta or None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

@router.post("/login", response_model=Token)
async def login_for_access_token(env: Annotated[Environment, Depends(odoo_env)], form_data: Annotated[OAuth2PasswordRequestForm, Depends()]):
    user = env["res.users"].sudo().search([("login", "=", form_data.username)], limit=1)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username",
            headers={"WWW-Authenticate": "Bearer"},
        )
    env.cr.execute("SELECT COALESCE(password, '') FROM res_users WHERE id=%s", [user.id])
    [hashed] = env.cr.fetchone()
    if not user._crypt_context().verify(form_data.password, hashed):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.login}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

async def get_current_user(env: Annotated[Environment, Depends(odoo_env)], token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = env["res.users"].sudo().search([("login", "=", username)], limit=1)
    if user is None:
        raise credentials_exception
    return User(id=user.id,
                username=user.login,
                email=user.email,
                full_name=user.name)

@router.post("/logout")
async def logout(current_user: Annotated[User, Depends(get_current_user)]):
    try:
        return {"message": "Logged out successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Logout failed")

@router.get("/module/list", response_model=list[ListModule])
def get_module(env: Annotated[Environment, Depends(odoo_env)], current_user: Annotated[User, Depends(get_current_user)]) -> list[ListModule]:
    try:
        return [ListModule(name=module.name if module.name else '',
                        shortdesc=module.shortdesc if module.shortdesc else '',
                        description=module.description if module.description else '',
                        author=module.author if module.author else '',
                        summary=module.summary if module.summary else '',
                        state=module.state if module.state else '',
                        latest_version=module.latest_version if module.latest_version else '') for module in env["ir.module.module"].sudo().search([])]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Module List not found!")

@router.get("/user/group/permission/list", response_model=list[ListUser])
def get_user_group_permission(env: Annotated[Environment, Depends(odoo_env)], current_user: Annotated[User, Depends(get_current_user)]) -> list[ListUser]:
    try:
        users = []
        for data in env["res.users"].sudo().search([('active', '=', True)]):
            env.cr.execute("SELECT md.name, im.model, im.name, rg.name, md.perm_read, md.perm_write, md.perm_create, md.perm_unlink FROM res_groups_users_rel AS grp INNER JOIN ir_model_access AS md ON md.group_id = grp.gid LEFT JOIN ir_model AS im ON im.id = md.model_id LEFT JOIN res_groups AS rg ON rg.id = md.group_id WHERE grp.uid = %s", (data.id,))
            results = env.cr.fetchall()
            model_access = []
            for grp in results:
                print(grp)
                model_access.append({
                    'name': grp[0],
                    'model': grp[1],
                    'model_name': str(grp[2]['en_US']),
                    'group_name': str(grp[3]['en_US']),
                    'perm_read': grp[4],
                    'perm_write': grp[5],
                    'perm_create': grp[6],
                    'perm_unlink': grp[7]
                })
            users.append({
                'id': data.id,
                'full_name': data.partner_id.name if data.partner_id else '',
                'email': data.login if data.login else '',
                'access_list': model_access
            })
        return users
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"User Group Permission List not found!")

@router.get("/profile", response_model=ListProfile)
def get_profile(env: Annotated[Environment, Depends(odoo_env)], current_user: Annotated[User, Depends(get_current_user)]) -> ListProfile:
    try:
        return ListProfile(id=current_user.id,
                        email=current_user.email,
                        username=current_user.username,
                        full_name=current_user.full_name)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Profile not found!")

@router.get("/employee/list", response_model=list[ListEmployee])
def get_employee(env: Annotated[Environment, Depends(odoo_env)], current_user: Annotated[User, Depends(get_current_user)]) -> list[ListEmployee]:
    try:
        return [ListEmployee(id=data.id,
                        name=data.name if data.name else '',
                        job_title=data.job_title if data.job_title else '',
                        work_phone=data.work_phone if data.work_phone else '',
                        mobile_phone=data.mobile_phone if data.mobile_phone else '',
                        work_email=data.work_email if data.work_email else '',
                        active=data.active if data.active else '') for data in env["hr.employee"].sudo().search([('employee_type', '=', 'employee')])]
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Employee List not found!")

@router.get("/employee/id/{id}", response_model=ListEmployee)
def get_employee_id(env: Annotated[Environment, Depends(odoo_env)], id: int, current_user: Annotated[User, Depends(get_current_user)]) -> ListEmployee:
    data = env["hr.employee"].with_user(current_user.id).browse(id)
    try:
        return ListEmployee(id=data.id,
                        name=data.name if data.name else '',
                        job_title=data.job_title if data.job_title else '',
                        work_phone=data.work_phone if data.work_phone else '',
                        mobile_phone=data.mobile_phone if data.mobile_phone else '',
                        work_email=data.work_email if data.work_email else '',
                        active=data.active if data.active else '')
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Employee not found!")

@router.post("/employee/create")
async def post_employee(env: Annotated[Environment, Depends(odoo_env)], data: PostEmployee, users: Annotated[User, Depends(get_current_user)]):
    if data.name == '':
        raise HTTPException(status_code=400, detail=f"Missing required fields: name")
    try:
        employee_id = env['hr.employee'].sudo().create({
            'name': data.name,
            'employee_type': 'employee',
            'job_title': data.job_title,
            'work_phone': data.work_phone,
            'mobile_phone': data.mobile_phone,
            'work_email': data.work_email,
            'active': True,
        })
        return {"message": "Employee created successfully", "record_id": employee_id.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating record: {str(e)}")

@router.put("/employee/update")
async def put_employee(env: Annotated[Environment, Depends(odoo_env)], data: PutEmployee, users: Annotated[User, Depends(get_current_user)]):
    if data.name == '':
        raise HTTPException(status_code=400, detail=f"Missing required fields: name")
    employee = env['hr.employee'].sudo().search([('id', '=', data.id)])
    if employee:
        try:
            employee.write({
                'name': data.name,
                'job_title': data.job_title,
                'work_phone': data.work_phone,
                'mobile_phone': data.mobile_phone,
                'work_email': data.work_email,
            })
            return {"message": "Employee updated successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error updating record: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail=f"Employee not found!")

@router.delete("/employee/delete")
async def delete_employee(env: Annotated[Environment, Depends(odoo_env)], data: DeleteEmployee, users: Annotated[User, Depends(get_current_user)]):
    if data.id == '':
        raise HTTPException(status_code=400, detail=f"Missing required fields: id")
    employee = env['hr.employee'].sudo().search([('id', '=', data.id)])
    if employee:
        try:
            employee.unlink()
            return {"message": "Employee deleted successfully"}
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error deleting record: {str(e)}")
    else:
        raise HTTPException(status_code=404, detail=f"Employee not found!")
