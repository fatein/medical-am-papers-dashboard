# 论文标注证据逐项复核（2026-11-05）

本轮处理上一轮留下的366项摘录定位问题和141项训练标签差异，共507项，涉及456篇论文。

每项分别核对摘录来源与标签含义。原文来源包括本地原PDF、出版社XML全文以及原始题名和摘要。PDF页码按实际文件物理页复核；XML和元数据引用不填写PDF页码。训练依据采用2026-11-04更新的第30批标注，文件校验值见同名JSON登记表。

最终处置为315项替换摘录、151项调整标签、26项保留、15项按既有约定跳过。两个任务可能对应同一论文同一字段，实际修改426篇论文、150个标签字段及相关引文定位。论文数量保持7,169篇。

已修正的典型问题包括口服剂型误归牙科、作者单位误作疾病证据、STL文件格式误作槽式光聚合、SLS本构模型缩写误作粉床熔融、参考文献或术中辅助材料误作打印成品材料。缺少可确认具体材料或工艺的项目改为U；生物打印按原有明确阳性判据核对。训练标签更窄而当前归类合理的项目予以保留。

少数论文只给出商品名或设备名，通过制造商一手资料交叉确认技术属性，Dashboard保留论文自身原句：

- [Asiga PRO 4K官方资料](https://support.asiga.com/pro-4k/)
- [NextDent C&B MFH材料说明](https://www.3dsystems.com/materials/nextdent-cb-mfh)
- [ProJet 3510 SD官方数据手册](https://www.3dsystems.com/sites/default/files/projet_3500_plastic_0115_usen_web.pdf)
- [Stratasys PolyJet材料与设备支持](https://support.stratasys.com/en/Materials/PolyJet/Biocompatible)
- [Formlabs Form 3技术说明](https://formlabs.com/blog/introducing-form-3-form-3l-low-force-stereolithography/)

中文、英文、德语页面共用本次修订的数据；论文原文摘录保留原语言。逐字段发布校验登记在[同名JSON](paper-evidence-recheck-2026-11-05.json)，完整本地逐条审查表保存在项目输出目录。
