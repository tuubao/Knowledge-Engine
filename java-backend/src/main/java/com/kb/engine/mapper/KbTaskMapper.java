package com.kb.engine.mapper;

import com.kb.engine.entity.KbTask;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface KbTaskMapper {

    int insert(KbTask task);

    int update(KbTask task);

    KbTask selectByTaskId(@Param("taskId") String taskId);
}
