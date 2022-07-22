import traceback

from flask import render_template,redirect
from flask_appbuilder.models.sqla.interface import SQLAInterface
from flask_appbuilder import ModelView, ModelRestApi
from flask_appbuilder import ModelView,AppBuilder,expose,BaseView,has_access
from importlib import reload
from flask_babel import gettext as __
from flask_babel import lazy_gettext as _
from flask_babel import lazy_gettext,gettext
from flask_appbuilder.forms import GeneralModelConverter
import uuid
from sqlalchemy import and_, or_, select
from flask_appbuilder.actions import action
import re,os
from wtforms.validators import DataRequired, Length, NumberRange, Optional,Regexp
from kfp import compiler
from sqlalchemy.exc import InvalidRequestError
# 将model添加成视图，并控制在前端的显示
from myapp import app, appbuilder,db,event_logger
from myapp.utils import core
from wtforms import BooleanField, IntegerField,StringField, SelectField,FloatField,DateField,DateTimeField,SelectMultipleField,FormField,FieldList
from flask_appbuilder.fieldwidgets import BS3TextFieldWidget,BS3PasswordFieldWidget,DatePickerWidget,DateTimePickerWidget,Select2ManyWidget,Select2Widget
from myapp.forms import MyBS3TextAreaFieldWidget,MySelect2Widget,MyCodeArea,MyLineSeparatedListField,MyJSONField,MyBS3TextFieldWidget,MySelectMultipleField
from wtforms.ext.sqlalchemy.fields import QuerySelectField
from myapp.views.view_dimension import Dimension_table_ModelView_Api


from .baseApi import (
    MyappModelRestApi
)
from flask import (
    current_app,
    abort,
    flash,
    g,
    Markup,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    Response,
    url_for,
)
from myapp import security_manager
from werkzeug.datastructures import FileStorage
from .base import (
    api,
    BaseMyappView,
    check_ownership,
    data_payload_response,
    DeleteMixin,
    generate_download_headers,
    get_error_msg,
    get_user_roles,
    handle_api_exception,
    json_error_response,
    json_success,
    MyappFilter,
    MyappModelView,
)
from myapp.models.model_metadata_metric import Metadata_metric
from flask_appbuilder import CompactCRUDMixin, expose
import pysnooper,datetime,time,json
from myapp.security import MyUser
conf = app.config
logging = app.logger


class Metadata_Metrics_table_Filter(MyappFilter):
    # @pysnooper.snoop()
    def apply(self, query, func):
        if g.user.is_admin():
            return query
        # 公开的，或者责任人包含自己的
        return query.filter(
            or_(
                self.model.public==True,
                self.model.metric_responsible.contains(g.user.username)
            )
        )



class Metadata_metric_ModelView_base():
    label_title='指标'
    datamodel = SQLAInterface(Metadata_metric)
    base_permissions = ['can_add','can_show','can_edit','can_list','can_delete']
    base_order = ("changed_on", "desc")
    # order_columns = ['id','changed_on']
    order_columns = ['id']
    search_columns=['metric_data_type','metric_responsible','app','name','label','describe','metric_type','metric_level','task_id','caliber']

    list_columns = ['app','metric_data_type','name','label','describe','metric_level','metric_responsible','public','metric_type','task_id']
    cols_width = {
        "name":{"type": "ellip2", "width": 200},
        "label": {"type": "ellip2", "width": 200},
        "describe": {"type": "ellip2", "width": 400},
        "metric_responsible": {"type": "ellip2", "width": 300}
    }
    spec_label_columns={
        "name":"指标英文名",
        "label": "指标中文名",
        "describe":"指标描述",
        "metric_data_type":"指标模块"
    }
    add_columns = ['app','metric_data_type','name','label','describe','metric_type','metric_level','metric_dim','metric_responsible','caliber','task_id','public']
    # show_columns = ['project','name','describe','config_html','dag_json_html','created_by','changed_by','created_on','changed_on','expand_html']
    edit_columns = add_columns
    base_filters = [["id", Metadata_Metrics_table_Filter, lambda: []]]  # 设置权限过滤器
    add_form_extra_fields = {
        "app": SelectField(
            label=_(datamodel.obj.lab('app')),
            description='产品',
            widget=Select2Widget(),
            choices=[[x,x] for x in ['QQ音乐', '酷狗音乐','全民K歌','酷我音乐','懒人畅听','基础架构']]
        ),
        "name":StringField(
            label=_(datamodel.obj.lab('name')),
            description='指标英文名',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "label": StringField(
            label=_(datamodel.obj.lab('label')),
            description='指标中文名',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "describe": StringField(
            label=_(datamodel.obj.lab('describe')),
            description='指标描述',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "metric_type": SelectField(
            label=_(datamodel.obj.lab('metric_type')),
            description='指标类型',
            default='原子指标',
            widget=Select2Widget(),
            choices=[[x,x] for x in ['原子指标', '衍生指标']]
        ),
        "metric_data_type": SelectField(
            label=_(datamodel.obj.lab('metric_data_type')),
            description='指标归属模块，<a href="%s">创建/查看 指标类型</a>'%conf.get('MODEL_URLS',{}).get('metric_data_type'),
            widget=MySelect2Widget(can_input=True),
            choices=[[x, x] for x in ['营收','规模','商业化']]
        ),
        "metric_level":SelectField(
            label=_(datamodel.obj.lab('metric_level')),
            description='指标重要级别',
            default='普通',
            widget=Select2Widget(),
            choices=[[x,x] for x in ['普通','重要','核心']]
        ),
        "metric_dim": SelectField(
            label=_(datamodel.obj.lab('metric_dim')),
            description='指标维度1',
            default='天',
            widget=Select2Widget(),
            choices=[[x, x] for x in ['天', '周', '月']]
        ),
        "metric_responsible": StringField(
            label=_(datamodel.obj.lab('metric_responsible')),
            description='指标负责人，逗号分隔',
            widget=BS3TextFieldWidget(),
            validators=[DataRequired()]
        ),
        "status": SelectField(
            label=_(datamodel.obj.lab('status')),
            description='指标状态',
            widget=Select2Widget(),
            choices=[[x,x] for x in [ "下线","待审批",'创建中',"上线",]]
        ),
        "caliber": StringField(
            label=_(datamodel.obj.lab('caliber')),
            description='指标口径描述，代码和计算公式',
            widget=MyBS3TextAreaFieldWidget(rows=3),
            validators=[DataRequired()]
        ),
        "task_id": StringField(
            label=_(datamodel.obj.lab('task_id')),
            description='任务id',
            widget=BS3TextFieldWidget()
        ),
    }

    edit_form_extra_fields = add_form_extra_fields
    import_data=True

    @expose("/upload/", methods=["POST"])
    def upload(self):
        csv_file = request.files.get('csv_file')  # FileStorage
        # 文件保存至指定路径
        i_path = csv_file.filename
        if os.path.exists(i_path):
            os.remove(i_path)
        csv_file.save(i_path)
        # 读取csv，读取header，按行处理
        import csv
        csv_reader = csv.reader(open(i_path, mode='r', encoding='utf-8-sig'))
        header = None
        result = []
        for line in csv_reader:
            if not header:
                header = line
                continue
            # 判断header里面的字段是否在数据库都有
            for col_name in header:
                # attr = self.datamodel.obj
                if not hasattr(self.datamodel.obj, col_name):
                    flash('csv首行header与数据库字段不对应', 'warning')
                    back = {
                        "status": 1,
                        "result": [],
                        "message": "csv首行header与数据库字段不对应"
                    }
                    return self.response(400, **back)
            data = dict(zip(header, line))

            try:
                data['public']=bool(int(data.get('public',1)))

                model = self.datamodel.obj(**data)
                self.pre_add(model)
                db.session.add(model)
                self.post_add(model)
                db.session.commit()
                result.append('success')
            except Exception as e:
                print(e)
                result.append('fail')

        flash('成功导入%s行，失败导入%s行' % (len([x for x in result if x == 'success']), len([x for x in result if x == 'fail'])), 'warning')
        back = {
            "status": 0,
            "result": result,
            "message": "result为上传成功行，共成功%s" % len([x for x in result if x == 'success'])
        }
        return self.response(200, **back)


    # @action(
    #     "mulcopy", __("Copy"), __("复制所有指标"), "fa-copy", single=False
    # )
    # def mulcopy(self, items):
    #     if not items:
    #         abort(404)
    #     for item in items:
    #         new_metric = item.clone()
    #         new_metric.name = new_metric.name+"-copy"
    #         db.session.commit()


    @action(
        "muldelete", __("Delete"), __("Delete all Really?"), "fa-trash", single=False
    )
    def muldelete(self, items):
        if not items:
            abort(404)
        for item in items:
            try:
                if item.created_by.username==g.user.username:
                    self.pre_delete(item)
                    self.datamodel.delete(item, raise_exception=True)
                    self.post_delete(item)
            except Exception as e:
                flash(str(e), "danger")

class Metadata_metric_ModelView_Api(Metadata_metric_ModelView_base,MyappModelRestApi):
    datamodel = SQLAInterface(Metadata_metric)
    route_base = '/metadata_metric_modelview/api'
    label_title='指标'


    # 添加可选值
    # @pysnooper.snoop()
    def add_more_info(self,response,**kwargs):
        from myapp.views.baseApi import API_RELATED_RIS_KEY,API_ADD_COLUMNS_RES_KEY,API_EDIT_COLUMNS_RES_KEY

        choices=list(Dimension_table_ModelView_Api.get_dim_target_data(2447)['metric_type'].values())
        print(choices)
        if not choices:
            return
        columns = response[API_ADD_COLUMNS_RES_KEY]
        for column in columns:
            if column['name']=='metric_data_type':
                column['values']=[
                    {
                        'id': x,
                        'value': x
                    } for x in list(set(choices))
                ]

        response[API_ADD_COLUMNS_RES_KEY]=columns

        # for col in response[API_ADD_COLUMNS_RES_KEY]:
        #     if col['name']=='columns':
        #         response[API_EDIT_COLUMNS_RES_KEY].remove(col)
        # for col in response[API_EDIT_COLUMNS_RES_KEY]:
        #     if col['name'] == 'columns':
        #         response[API_EDIT_COLUMNS_RES_KEY].remove(col)


appbuilder.add_api(Metadata_metric_ModelView_Api)







